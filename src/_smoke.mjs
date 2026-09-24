import { Context, Service } from 'cordis'
import Loader from '@cordisjs/plugin-loader'
import ConsoleExporter from '@cordisjs/plugin-logger-console'
import { pathToFileURL } from 'node:url'

const ctx = new Context()
await ctx.plugin(ConsoleExporter)

// 1) 直接注册类服务插件（必须 await，效果异步执行）
class Demo extends Service {
  static provide = 'demo'
  constructor(c, config) {
    super(c, 'demo')
    this.config = config
  }
  hello() {
    return 'direct-service-ok'
  }
}
await ctx.plugin(Demo, { tag: 'smoke' })
console.log('[smoke] ctx.demo.hello() =>', ctx.demo?.hello())
console.log('[smoke] ctx.demo.config =>', JSON.stringify(ctx.demo?.config))

// 2) 用 loader 通过相对路径加载本地插件
await ctx.plugin(Loader, { baseUrl: pathToFileURL(process.cwd() + '/').href })
const loader = ctx.loader
console.log('[smoke] ctx.loader present =>', !!loader)
await loader.create({ id: 'lp', name: './src/_local_plugin.mjs', config: { a: 1 } })
await loader.await()
console.log('[smoke] entries count =>', [...loader.root.tree.entries()].length)
console.log('[smoke] ctx.demo2.ping() =>', ctx.demo2?.ping())

// 注：Cordis 根 Context 没有 dispose()（根 fiber dispose=restart），冒烟测试直接退出即可
console.log('[smoke] disposed OK')
process.exit(0)
