# Official SOLIDWORKS API workflow

Use SWCLI's capability catalog and operation contract to identify the exact gap.
An unadvertised operation or a documented scope limit does not establish that
SOLIDWORKS lacks the capability. Check the official API help for the version
running on the target host and verify the interface, arguments, and side effects.

## Official documentation entry points

For a SOLIDWORKS 2025 host, start with these official references. Select the
installed version when the target host differs.

- [SOLIDWORKS API overview](https://help.solidworks.com/2025/english/SolidWorks/sldworks/c_solidworks_api.htm?format=P) describes the native COM programming interface.
- [API getting started](https://help.solidworks.com/2025/english/api/sldworksapiprogguide/GettingStarted/SolidWorks_API_Getting_Started_Overview.htm?id=1.0) introduces API development and the SDK.
- [Interface navigation](https://help.solidworks.com/2025/english/api/sldworksapiprogguide/GettingStarted/Understanding_the_SolidWorks_API_Class_Hierarchy.htm?id=1.3.1) explains interface access. Follow a member page's Accessors links to obtain the required object.
- [API access diagram](https://help.solidworks.com/2025/english/api/sldworksapi/SWObjectModel.pdf) maps the native objects and their access paths.

Search the official help for the exact interface and member name. Before a
call, check version availability, argument order, output/reference parameters,
return codes, units and enum values. Follow the member's documented examples
and verify its postcondition on the intended model.

If Web Help returns only its navigation shell, use the installed API Help CHM
or type libraries for the same SOLIDWORKS version. Keep the member's official
URL with the task's implementation or verification notes.

## Native execution

Use a native API client in the host's SOLIDWORKS environment. For Wine, follow
the host product's runtime and prefix rules. A remote SWCLI endpoint does not
provide COM access, and the typed protocol has no arbitrary COM request. Attach
to the existing instance and verify its identity and the target document before
calling the API. If you cannot verify them, report the specific access blocker.

For inspection, prefer getters. A direct client does not share SWCLI leases.
For authorized changes, ensure exclusive access to the target operation,
keep the change within the user's requested scope, and verify the native result.
Never use direct COM to circumvent a lease, stale handle, permission check,
timeout, or failed typed edit. Report results from the CLI and native API separately.

Motion studies and exploded views are separate queries. Use
[IModelDocExtension.GetMotionStudyManager](https://help.solidworks.com/2019/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDocExtension~GetMotionStudyManager.html)
and the [Motion Study Manager](https://help.solidworks.com/2025/english/api/swmotionstudyapi/SolidWorks.Interop.swmotionstudy~SolidWorks.Interop.swmotionstudy.IMotionStudyManager.html)
to enumerate studies. Check the study type if Simulation studies must be
excluded. For exploded views use
[IAssemblyDoc.GetExplodedViewNames2](https://help.solidworks.com/2021/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IAssemblyDoc~GetExplodedViewNames2.html)
for the requested configuration.
