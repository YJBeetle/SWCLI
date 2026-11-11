"""Static pinned MSFT-TLB/.NET metadata inspection. No COM, DLL loading or CAD.

Requires dnfile for PE metadata only. Inputs are read; only --output is written.
The small MSFT reader handles the two pinned methods, not arbitrary typelibs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import uuid

TLB_SHA = '585e008c1322754e313dfb23d34b681b40fe4664a9c32d2c00f6250cb8741159'
INTEROP_SHA = 'a53c7c179ead50e7df9266c1b79e9d6a865ca591b1f2bcd96804fdb3803b15e1'


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def typelib(raw):
    check(digest(raw) == TLB_SHA and raw[:4] == b'MSFT', 'Expected pinned actual TLB')
    u = lambda pos: struct.unpack_from('<I', raw, pos)[0]
    count = u(32)
    directory = 84 + 4*count + (4 if u(20)&0x100 else 0)
    segments = [struct.unpack_from('<4i',raw,directory+16*i)[:2] for i in range(15)]
    def name(offset):
        pos = segments[7][0] + offset
        length = u(pos+8)&255
        return raw[pos+12:pos+12+length].decode('cp1252')
    def info(href):
        check(href%100 == 0 and href//100 < count, 'Unsupported external type reference')
        pos = segments[0][0]+href
        return dict(name=name(u(pos+52)),guid=str(uuid.UUID(bytes_le=raw[segments[5][0]+u(pos+44):segments[5][0]+u(pos+44)+16])))
    vartypes = {3:'VT_I4',8:'VT_BSTR',9:'VT_DISPATCH',25:'VT_HRESULT'}
    def datatype(encoded, depth=0):
        check(depth<5,'Unexpected type recursion')
        if encoded & 0x80000000:
            vt = encoded & 0xffff
            check(vt in vartypes,'Unexpected inline type')
            return dict(type=vartypes[vt],encoded=hex(encoded))
        check(encoded+8 <= segments[9][1], 'Type descriptor out of bounds')
        pos = segments[9][0]+encoded
        kind,flags,target = struct.unpack_from('<HHI',raw,pos)
        result = dict(type='VT_PTR' if kind == 26 else 'VT_USERDEFINED',offset=encoded,raw_hex=raw[pos:pos+8].hex())
        check(kind in (26,29),'Unexpected descriptor kind')
        if kind == 26:result['target'] = datatype(target,depth+1)
        else:result['reference'] = info(target)
        return result
    result = {}
    for index in range(count):
        pos = segments[0][0]+index*100
        if name(u(pos+52)) != 'ISldWorks':continue
        mem = u(pos+4);n = u(pos+24)&65535;cursor = mem+4;records = []
        check(u(pos+24)>>16 == 0, 'Unexpected variable records')
        for _ in range(n):
            size = struct.unpack_from('<H',raw,cursor)[0]
            check(size>=24,'Invalid method record')
            records.append((cursor,size));cursor += size
        check(cursor == mem+4+u(mem),'Function region size differs')
        for number,(rec,size) in enumerate(records):
            method_name = name(u(cursor+4*n+4*number))
            if method_name not in ('LoadFile4','GetImportFileData'):continue
            argc,opt = struct.unpack_from('<HH',raw,rec+20)
            parameters = []
            for param in range(argc):
                dt,nm,flags = struct.unpack_from('<III',raw,rec+size-argc*12+param*12)
                parameters.append(dict(name=name(nm),flags=flags,in_=bool(flags&1),out=bool(flags&2),retval=bool(flags&8),datatype=datatype(dt)))
            result[method_name] = dict(interface=info(index*100),dispid=u(cursor+4*number),record_offset=rec,
                record_hex=raw[rec:rec+size].hex(),return_type=datatype(u(rec+4)),optional_count=opt,parameters=parameters)
    load = result['LoadFile4']
    check(load['dispid'] == 227 and load['optional_count'] == 0,'Unexpected LoadFile4 identity')
    check([(p['name'],p['flags']) for p in load['parameters']] == [('FileName',1),('ArgString',1),('ImportData',1),('Errors',3),('Retval',10)],'Parameter names/flags differ')
    check(load['parameters'][2]['datatype']['type'] == 'VT_DISPATCH','ImportData is not IDispatch')
    check(load['parameters'][3]['datatype']['target']['type'] == 'VT_I4','Errors type differs')
    return result


def interop(path):
    import dnfile
    pe = dnfile.dnPE(str(path))  # Metadata parser only; never loads this assembly.
    def attr(row):
        result = {}
        for ca in pe.net.mdtables.CustomAttribute:
            if ca.Parent.row is not row:continue
            try:nm = str(ca.Type.row.Class.row.TypeName)
            except AttributeError:continue
            blob = ca.Value.value
            if nm == 'GuidAttribute':result['guid'] = blob[3:3+blob[2]].decode()
            if nm == 'DispIdAttribute':result['dispid'] = struct.unpack('<i',blob[2:6])[0]
        return result
    interface = next(row for row in pe.net.mdtables.TypeDef if str(row.TypeName) == 'ISldWorks')
    result = dict(interface=attr(interface),methods={})
    expected = {'LoadFile4':'20041286500e0e1c1008','GetImportFileData':'20011c0e'}
    def compressed(data,index):
        value = data[index];index += 1
        if value&0x80 == 0:return value,index
        if value&0xc0 == 0x80:return ((value&0x3f)<<8)|data[index],index+1
        return ((value&0x1f)<<24)|(data[index]<<16)|(data[index+1]<<8)|data[index+2],index+3
    def managed_type(data,index):
        kind = data[index];index += 1
        simple = {1:'void',2:'bool',8:'int32',14:'string',28:'object'}
        if kind in simple:return simple[kind],index
        if kind == 16:
            child,index = managed_type(data,index)
            return 'byref '+child,index
        check(kind in (17,18),'Unexpected managed signature type')
        coded,index = compressed(data,index)
        check(coded&3 in (0,1),'Unsupported managed type reference')
        table = pe.net.mdtables.TypeDef if coded&3 == 0 else pe.net.mdtables.TypeRef
        return str(table.rows[(coded>>2)-1].TypeName),index
    for item in interface.MethodList:
        row = item.row;nm = str(row.Name)
        if nm not in expected:continue
        data = row.Signature.value
        signature = expected[nm]
        check(data.hex() == signature and data[0] == 0x20,'Pinned method signature changed')
        count,index = compressed(data,1)
        ret,index = managed_type(data,index);types = [ret]
        for _ in range(count):
            arg,index = managed_type(data,index);types.append(arg)
        check(index == len(data),'Unparsed managed signature bytes')
        parameters = []
        for param in row.ParamList:
            param = param.row
            marshal = next((m.NativeType.value.hex() for m in pe.net.mdtables.FieldMarshal if m.Parent.row is param),None)
            parameters.append(dict(sequence=int(param.Sequence),name=str(param.Name),type=types[int(param.Sequence)],
                in_=bool(param.Flags.pdIn),out=bool(param.Flags.pdOut),marshal_blob=marshal))
        result['methods'][nm] = dict(signature_hex=signature,parameters=parameters,**attr(row))
    load = result['methods']['LoadFile4']
    check(load['dispid'] == 227 and load['parameters'][3]['name'] == 'ImportData' and load['parameters'][3]['marshal_blob'] == '1a', 'Interop ImportData marshal differs')
    assembly = pe.net.mdtables.Assembly.rows[0]
    result['assembly_version'] = '.'.join(str(x) for x in (assembly.MajorVersion,assembly.MinorVersion,assembly.BuildNumber,assembly.RevisionNumber))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tlb',type=Path,required=True)
    parser.add_argument('--interop',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    check(args.output.resolve() not in (args.tlb.resolve(),args.interop.resolve()),'Must not overwrite installed input')
    inputs = {key:dict(path=str(path),sha256=digest(path.read_bytes())) for key,path in [('tlb',args.tlb),('interop',args.interop)]}
    check(inputs['interop']['sha256'] == INTEROP_SHA,'Expected pinned local installed interop')
    result = dict(kind='static file inspection only; zero native/COM calls',inputs=inputs,tlb=typelib(args.tlb.read_bytes()),interop=interop(args.interop),
        limitations=['Local TLB bytes equal VM recorded hash; VM interop DLL hash not recorded, so interop byte identity is not asserted',
                     'ABI type declarations cannot settle conditional 3DI/null behavioral documentation conflicts'])
    check(result['interop']['interface']['guid'].lower() == result['tlb']['LoadFile4']['interface']['guid'],'TLB/interop interface identity differs')
    final_hashes = {key:digest(path.read_bytes()) for key,path in [('tlb',args.tlb),('interop',args.interop)]}
    check(all(final_hashes[key] == row['sha256'] for key,row in inputs.items()),'Installed files changed during inspection')
    result['input_hashes_unchanged_after_inspection'] = True
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('Static TLB/interop inspection PASS: ImportData IDispatch; two BSTR; in/out I4; no CAD')


if __name__ == '__main__':
    main()
