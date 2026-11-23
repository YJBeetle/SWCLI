# 后续 writable-read 模式：设计门禁，尚未实现/验收

公共B当前只支持实际readonly ASM及readonly source，token的read_gate明确不授权写。将readonly ASM关闭再打开writable会取得新native document/registry scope；旧as-/at-token失效，不能把B的六面读取结果直接拿去CreateMate。37的原始core与readonly门禁保持原样。

为后续既定coincident/concentric闭环，单独准备显式模式 `writable-read` 的契约；本文件只记录设计，不注册此请求字段、不改37函数、不发此类token，也不安排VM/CI。

1. 保留现有 `readonly` 模式为默认及37原行为。新模式必须由公共请求显式选择并返回实际观察模式；ASM必须saved/clean、non-view-only、已经active，原生IsOpenedReadOnly必须严格False。source继续严格saved/clean/readonly，分别返回ASM与每份source的原始标志；未知、混用、反向标志一律拒绝。读取自身零选取、零模型写入、零保存，不设置readonly属性来满足契约。
2. 新模式仍需同一owning STA、33.5.0官方接口、完整两实例/全face、来源→mapped→typed reference→resolved IEntity唯一owner/精确native IsSame及全部后置。ASM配置/stamp/path/dirty/edit/source/pose/fixed/suppression和前景均前后不变。模式属于snapshot scope，readonly与writable-read token不能互认或静默转换；重开/代次变化全部失效。
3. 独立新候选实现与离线反例后，主协调亲审精确源码/原件/once-only计划，另发许可，公共路径真实实开writable ASM、readonly source做新只读native门禁。保存样件原件哈希、flags、全face owner/read、前后unchanged、异常零partial、held exit/native前后必须原始留证。37 readonly通过不能代替这一证明。
4. 新模式原生通过以后，写入口仍须另读完整既有mate树定义/状态，连同全target/source/实例/配置/stamp/pose做完整CAS；预期dirty的观察政策必须另有显式前后契约。lease与旧typed handles/session/document/worker检查、写UI/edit/selection/writable守卫、紧贴首次CAD写的already-active检查均不能由writable-read代替。
5. 最后才为既定plane coincident与cylinder concentric逐个安排一次CreateMate、原始错误/partial mutation、写后native定义/solver/几何/源保护、save/close/reopen独立门禁；不扩类型、不回滚、不重试，不恢复旧分支公共实现。

因此当前实现状态是：readonly public B本地候选；writable-read仅设计；mate-tree写CAS、配合写入及保存重开尚未实现或验收。
