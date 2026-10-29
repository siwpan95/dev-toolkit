// 本地插件（供 loader 通过相对路径加载测试）
import { Service } from 'cordis'

export class LocalService extends Service {
  static provide = 'demo2'
  constructor(ctx, config) {
    super(ctx, 'demo2')
    this.config = config
  }
  ping() {
    return 'local-plugin-ok'
  }
}

export default LocalService
