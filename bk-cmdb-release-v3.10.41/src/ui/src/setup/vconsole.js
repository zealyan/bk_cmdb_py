/*
 * vConsole 移动端调试工具初始化
 * 仅在开发环境启用，提供移动端调试能力
 */

if (process.env.NODE_ENV === 'development') {
  import('vconsole').then((module) => {
    const VConsole = module.default
    window.vConsole = new VConsole({
      defaultPlugins: ['system', 'network', 'element', 'storage'],
      maxLogNumber: 1000,
      onReady: () => {
        console.log('[vConsole] vConsole 已启动，可在右下角查看')
      }
    })
  }).catch((err) => {
    console.warn('[vConsole] 加载失败:', err)
  })
}
