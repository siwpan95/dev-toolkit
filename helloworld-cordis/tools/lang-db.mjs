// lang-db.mjs — 「语言 → 运行方式」知识库（静态事实，不含任何 Cordis 代码）
//
// 这是 helloworld-cordis 唯一的"领域知识"落点：告诉组合层每种语言该由谁来执行。
// 一条记录 = 一种语言的一份好奇心：它是什么家族、要什么工具链、跑起来该敲什么命令。
//
// 每条记录的字段：
//   lang       人类可读语言名
//   family     script | vm | compiled | markup | query | esolang
//   carrier    工具链齐备时优先使用的载体
//                embedded  = 运行时加载进 Cordis 主进程（零 IPC）
//                subprocess= 每次调用 fork/exec 一个外部解释器（冷启动）
//                gateway   = 长驻 JSON-stdio worker（预热，免去解释器冷启动）
//   requires   探针键：宿主可执行文件 npm:<pkg>/node, 或 PATH 上的程序名，
//                      或 node:sqlite / node:vm / npm:fengari 这类内建能力
//   run        运行模板，{file} 会替换成 helloworld 下的绝对路径
//   build      可选：编译模板（挂载时执行一次）
//   note       人类可读备注（多为"本机缺什么工具链"）
//
// ⚠️ 架构边界：helloworld/ 下的 76 个源文件一个字节都不改，零依赖、cordis-unaware。
//    如何把它们导通，全部由本库和 src/ports/* 负责 —— 与参考项目 chess-cordis 一致。

/** @type {Record<string, {lang:string, family:string, carrier:string, requires:string, run?:string[], build?:string[], note?:string}>} */
export const LANG_DB = {
  // ---------- 本机当前可真正执行（已实测） ----------
  python: {
    lang: 'Python', family: 'script', carrier: 'subprocess', requires: 'python',
    run: ['python', '{file}'],
  },
  javascript: {
    lang: 'JavaScript', family: 'script', carrier: 'embedded', requires: 'node:vm',
    run: null,
    note: '宿主 Node 即该语言的运行时，走 node:vm 进程内执行（零 IPC）',
  },
  typescript: {
    lang: 'TypeScript', family: 'script', carrier: 'subprocess', requires: 'node',
    run: ['{node}', '{file}'],
    note: 'Node ≥22.18 的类型擦除直跑，无需 esbuild',
  },
  bash: {
    lang: 'Bash', family: 'script', carrier: 'subprocess', requires: 'bash',
    run: ['bash', '{file}'],
  },
  powershell: {
    lang: 'PowerShell', family: 'script', carrier: 'subprocess', requires: 'powershell',
    run: ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', '{file}'],
    note: 'Windows PowerShell 5.1（pwsh 7 未安装）',
  },
  lua: {
    lang: 'Lua', family: 'vm', carrier: 'embedded', requires: 'npm:fengari',
    run: null,
    note: 'fengari = 纯 JS 实现的 Lua 5.3 VM，随 npm 可选依赖装入',
  },
  sql: {
    lang: 'SQL', family: 'query', carrier: 'embedded', requires: 'node:sqlite',
    run: null,
    note: 'Node 内建 node:sqlite（SQLite 引擎），SELECT 结果取首列作为输出',
  },
  ruby: {
    lang: 'Ruby', family: 'script', carrier: 'embedded', requires: 'npm:@ruby/3.2-wasm-wasi',
    run: null,
    note: '官方 Ruby WASM 版（约 96MB）；本机未安装 → 自动降级为 disabled',
  },

  // ---------- 常规解释型 / 虚拟机型（本机无工具链） ----------
  perl:     { lang: 'Perl',     family: 'script', carrier: 'subprocess', requires: 'perl',     run: ['perl', '{file}'] },
  php:      { lang: 'PHP',      family: 'script', carrier: 'subprocess', requires: 'php',      run: ['php', '{file}'] },
  rubybin:  { lang: 'Ruby(本地解释器)', family: 'script', carrier: 'subprocess', requires: 'ruby', run: ['ruby', '{file}'], note: '需本机 ruby 而非 WASM 版' },
  r:        { lang: 'R',        family: 'script', carrier: 'subprocess', requires: 'Rscript',  run: ['Rscript', '{file}'] },
  julia:    { lang: 'Julia',    family: 'script', carrier: 'subprocess', requires: 'julia',    run: ['julia', '{file}'] },
  tcl:      { lang: 'Tcl',      family: 'script', carrier: 'subprocess', requires: 'tclsh',    run: ['tclsh', '{file}'] },
  elixir:   { lang: 'Elixir',   family: 'vm',     carrier: 'subprocess', requires: 'elixir',   run: ['elixir', '{file}'] },
  erlang:   { lang: 'Erlang',   family: 'vm',     carrier: 'subprocess', requires: 'escript',  run: ['escript', '{file}'] },
  raku:     { lang: 'Raku',     family: 'vm',     carrier: 'subprocess', requires: 'raku',     run: ['raku', '{file}'] },
  groovy:   { lang: 'Groovy',   family: 'vm',     carrier: 'subprocess', requires: 'groovy',   run: ['groovy', '{file}'] },
  clojure:  { lang: 'Clojure',  family: 'vm',     carrier: 'subprocess', requires: 'clojure',  run: ['clojure', '-M', '{file}'] },
  scala:    { lang: 'Scala',    family: 'vm',     carrier: 'subprocess', requires: 'scala-cli',run: ['scala-cli', 'run', '{file}'] },
  lisp:     { lang: 'Common Lisp', family: 'vm',  carrier: 'subprocess', requires: 'sbcl',     run: ['sbcl', '--script', '{file}'] },
  scheme:   { lang: 'Scheme',   family: 'vm',     carrier: 'subprocess', requires: 'guile',    run: ['guile', '--no-auto-compile', '-l', '{file}'] },
  smalltalk:{ lang: 'Smalltalk',family: 'vm',     carrier: 'subprocess', requires: 'gst',      run: ['gst', '-f', '{file}'], note: 'GNU Smalltalk' },
  prolog:   { lang: 'Prolog',   family: 'vm',     carrier: 'subprocess', requires: 'swipl',    run: ['swipl', '-q', '-g', 'main', '-t', 'halt', '-s', '{file}'] },
  logo:     { lang: 'Logo',     family: 'vm',     carrier: 'subprocess', requires: 'ucblogo',  run: ['ucblogo', '{file}'] },
  gdscript: { lang: 'GDScript', family: 'vm',     carrier: 'subprocess', requires: 'godot',    run: ['godot', '--headless', '--script', '{file}'] },
  hack:     { lang: 'Hack',     family: 'vm',     carrier: 'subprocess', requires: 'hhvm',     run: ['hhvm', '{file}'] },
  mumps:    { lang: 'MUMPS',    family: 'vm',     carrier: 'subprocess', requires: 'gtm',      run: ['gtm', '-run', '{file}'], note: 'GT.M' },
  matlab:   { lang: 'MATLAB',   family: 'vm',     carrier: 'subprocess', requires: 'matlab',   run: ['matlab', '-batch', 'run("{file}")'] },
  dart:     { lang: 'Dart',     family: 'vm',     carrier: 'subprocess', requires: 'dart',     run: ['dart', 'run', '{file}'] },

  // ---------- 编译型（本机无工具链，声明 build+run 配方） ----------
  c:        { lang: 'C',        family: 'compiled', carrier: 'subprocess', requires: 'gcc',
              build: ['gcc', '-O2', '-o', '{out}', '{file}'], run: ['{out}'] },
  cpp:      { lang: 'C++',      family: 'compiled', carrier: 'subprocess', requires: 'g++',
              build: ['g++', '-O2', '-std=c++17', '-o', '{out}', '{file}'], run: ['{out}'] },
  rust:     { lang: 'Rust',     family: 'compiled', carrier: 'subprocess', requires: 'rustc',
              build: ['rustc', '-O', '-o', '{out}', '{file}'], run: ['{out}'] },
  go:       { lang: 'Go',       family: 'compiled', carrier: 'subprocess', requires: 'go',
              run: ['go', 'run', '{file}'] },
  zig:      { lang: 'Zig',      family: 'compiled', carrier: 'subprocess', requires: 'zig',
              run: ['zig', 'run', '{file}'] },
  nim:      { lang: 'Nim',      family: 'compiled', carrier: 'subprocess', requires: 'nim',
              run: ['nim', 'c', '-r', '--hints:off', '{file}'] },
  odin:     { lang: 'Odin',     family: 'compiled', carrier: 'subprocess', requires: 'odin',
              build: ['odin', 'build', '{file}', '-file', '-out:{out}'], run: ['{out}'] },
  crystal:  { lang: 'Crystal',  family: 'compiled', carrier: 'subprocess', requires: 'crystal',
              run: ['crystal', 'run', '{file}'] },
  haskell:  { lang: 'Haskell',  family: 'compiled', carrier: 'subprocess', requires: 'runghc',
              run: ['runghc', '{file}'] },
  ocaml:    { lang: 'OCaml',    family: 'compiled', carrier: 'subprocess', requires: 'ocaml',
              run: ['ocaml', '{file}'] },
  fsharp:   { lang: 'F#',       family: 'compiled', carrier: 'subprocess', requires: 'dotnet',
              run: ['dotnet', 'fsi', '--exec', '{file}'] },
  csharp:   { lang: 'C#',       family: 'compiled', carrier: 'subprocess', requires: 'dotnet',
              run: ['dotnet', 'run', '{file}'], note: '需 .NET SDK（本机 dotnet 缺失）' },
  vb:       { lang: 'VB.NET',   family: 'compiled', carrier: 'subprocess', requires: 'vbc',
              build: ['vbc', '-nologo', '-optimize', '-out:{out}', '{relfile}'], run: ['{out}'],
              note: '本机实到：C:/Windows/Microsoft.NET/Framework64/v4.0.30319/vbc.exe（.NET Framework 4.x）' },
  java:     { lang: 'Java',     family: 'compiled', carrier: 'subprocess', requires: 'javac',
              build: ['javac', '-d', '{outdir}', '{file}'], run: ['java', '-cp', '{outdir}', 'HelloWorld'],
              note: '源文件 public class HelloWorld 与文件名不一致，需 javac 到 classpath 再跑' },
  kotlin:   { lang: 'Kotlin',   family: 'compiled', carrier: 'subprocess', requires: 'kotlinc',
              build: ['kotlinc', '{file}', '-include-runtime', '-d', '{out}.jar'], run: ['java', '-jar', '{out}.jar'] },
  swift:    { lang: 'Swift',    family: 'compiled', carrier: 'subprocess', requires: 'swift',
              run: ['swift', '{file}'] },
  objectivec: { lang: 'Objective-C', family: 'compiled', carrier: 'subprocess', requires: 'clang',
              build: ['clang', '-fobjc-arc', '-o', '{out}', '{file}', '-lobjc'], run: ['{out}'] },
  pascal:   { lang: 'Pascal',   family: 'compiled', carrier: 'subprocess', requires: 'fpc',
              build: ['fpc', '-o{out}', '{file}'], run: ['{out}'] },
  fortran:  { lang: 'Fortran',  family: 'compiled', carrier: 'subprocess', requires: 'gfortran',
              build: ['gfortran', '-o', '{out}', '{file}'], run: ['{out}'] },
  cobol:    { lang: 'COBOL',    family: 'compiled', carrier: 'subprocess', requires: 'cobc',
              build: ['cobc', '-x', '-free', '-o', '{out}', '{file}'], run: ['{out}'] },
  ada:      { lang: 'Ada',      family: 'compiled', carrier: 'subprocess', requires: 'gnatmake',
              build: ['gnatmake', '-q', '-o', '{out}', '{file}'], run: ['{out}'] },
  // Mercury 编译器叫 mmc —— 与 Windows 的 Microsoft Management Console(mmc.exe) 同名。
  // 自动探测会把系统程序误判成 Mercury 工具链，且贸然执行它有拉起 GUI 的风险，
  // 因此显式声明"不探测"，避免假绿。
  mercury:  { lang: 'Mercury',  family: 'compiled', carrier: 'subprocess', requires: 'never:Mercury 编译器 mmc 与 Windows 的 mmc.exe 同名，自动探测不可靠',
              build: ['mmc', '--make', '{file}'], run: ['{out}'] },
  basic:    { lang: 'BASIC',    family: 'compiled', carrier: 'subprocess', requires: 'fbc',
              build: ['fbc', '{file}'], run: ['{out}'], note: 'FreeBASIC' },
  pli:      { lang: 'PL/I',     family: 'compiled', carrier: 'subprocess', requires: 'plic',
              build: ['plic', '-o', '{out}', '{file}'], run: ['{out}'] },
  agda:     { lang: 'Agda',     family: 'compiled', carrier: 'subprocess', requires: 'agda',
              run: ['agda', '--compile', '{file}'] },
  idris:    { lang: 'Idris',    family: 'compiled', carrier: 'subprocess', requires: 'idris2',
              build: ['idris2', '--cg', 'chez', '-o', 'main', '{file}'], run: ['{out}'] },
  clean:    { lang: 'Clean',    family: 'compiled', carrier: 'subprocess', requires: 'clm',
              build: ['clm', '-o', 'main', '{file}'], run: ['{out}'] },
  curry:    { lang: 'Curry',    family: 'compiled', carrier: 'subprocess', requires: 'curry',
              run: ['curry', 'run', '{file}'] },
  d:        { lang: 'D',        family: 'compiled', carrier: 'subprocess', requires: 'rdmd',
              run: ['rdmd', '{file}'] },
  hare:     { lang: 'Hare',     family: 'compiled', carrier: 'subprocess', requires: 'hare',
              run: ['hare', 'run', '{file}'] },
  vala:     { lang: 'Vala',     family: 'compiled', carrier: 'subprocess', requires: 'valac',
              build: ['valac', '-o', '{out}', '{file}'], run: ['{out}'] },
  asm:      { lang: 'Assembly', family: 'compiled', carrier: 'subprocess', requires: 'nasm',
              note: '目标平台相关的汇编，需 nasm + ld 链接；配方随平台而定' },
  bcpl:     { lang: 'BCPL',     family: 'compiled', carrier: 'subprocess', requires: 'bcpl',
              note: '需 BCPL 工具链（极冷门，本机无）' },
  simula:   { lang: 'Simula',   family: 'compiled', carrier: 'subprocess', requires: 'cim',
              build: ['cim', '{file}'], run: ['{out}'] },
  elm:      { lang: 'Elm',      family: 'compiled', carrier: 'subprocess', requires: 'elm',
              note: 'Elm 是转译到 JS 的前端语言，无 CLI 直接输出；需 node + 打包步骤' },
  sol:      { lang: 'Solidity', family: 'compiled', carrier: 'subprocess', requires: 'solc',
              note: '智能合约语言，需 solc + EVM 才能真跑；本文件只声明了返回字符串的 contract' },
  solidity: { lang: 'Solidity', family: 'compiled', carrier: 'subprocess', requires: 'solc',
              note: '智能合约语言，需 solc + EVM 才能真跑；本文件只声明了返回字符串的 contract' },
  algol68:  { lang: 'Algol 68', family: 'compiled', carrier: 'subprocess', requires: 'a68g',
              run: ['a68g', '{file}'], note: '需 Algol 68 Genie' },
  postscript: { lang: 'PostScript', family: 'vm',  carrier: 'subprocess', requires: 'gs',
              run: ['gs', '-q', '-dBATCH', '-dNOPAUSE', '-sDEVICE=txtwrite', '-sOutputFile=-', '{file}'],
              note: '需 Ghostscript' },
  forth:    { lang: 'Forth',    family: 'vm',      carrier: 'subprocess', requires: 'gforth', run: ['gforth', '{file}'] },
  xml:      { lang: 'XML/XSLT', family: 'markup',  carrier: 'subprocess', requires: 'xsltproc',
              note: '是 XSLT 样式表，需 xsltproc 之类处理器' },

  // ---------- 深奥语言 / 需要专门解释器 ----------
  brainfuck:{ lang: 'Brainfuck',family: 'esolang', carrier: 'embedded', requires: 'npm:none',
              note: 'esolang：可写 tiny VM 适配器驱动（本轮未实现）' },
  befunge:  { lang: 'Befunge',  family: 'esolang', carrier: 'subprocess', requires: 'bef',
              note: 'esolang：需 Befunge-98 解释器' },
  malbolge: { lang: 'Malbolge', family: 'esolang', carrier: 'subprocess', requires: 'malbolge',
              note: 'esolang：需 Malbolge 解释器' },
  ook:      { lang: 'Ook!',     family: 'esolang', carrier: 'subprocess', requires: 'ook',
              note: 'esolang：需 Ook! 解释器' },
  intercal: { lang: 'INTERCAL', family: 'esolang', carrier: 'subprocess', requires: 'ick',
              note: 'esolang：需 C-INTERCAL' },
  lolcode:  { lang: 'LOLCODE',  family: 'esolang', carrier: 'subprocess', requires: 'lci',
              note: 'esolang：需 lci 解释器' },
  shakespeare: { lang: 'Shakespeare', family: 'esolang', carrier: 'subprocess', requires: 'spl',
              note: 'esolang：需 Shakespeare 转译器' },
};

// 由文件名反推 lang slug：deepseek_<slug>_<YYYYMMDD>_<hash>.<ext>
export function slugOf(filename) {
  const m = /^deepseek_([a-z0-9]+)_(\d{8})_[0-9a-f]{6}\.(?:[A-Za-z0-9]+)$/.exec(filename);
  return m ? m[1] : null;
}
