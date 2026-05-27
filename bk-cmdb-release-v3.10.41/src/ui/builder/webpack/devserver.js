/*
 * Tencent is pleased to support the open source community by making 蓝鲸 available.
 * Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
 * Licensed under the MIT License (the "License"); you may not use this file except
 * in compliance with the License. You may obtain a copy of the License at
 * http://opensource.org/licenses/MIT
 * Unless required by applicable law or agreed to in writing, software distributed under
 * the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
 * either express or implied. See the License for the specific language governing permissions and
 * limitations under the License.
 */

const path = require('path')

const { HOST } = process.env
const PORT = process.env.PORT && Number(process.env.PORT)
const SKIP_LOGIN = process.env.SKIP_LOGIN === 'true'

module.exports = config => ({
  before(app) {
    const launchMiddleware = require('launch-editor-middleware')
    app.use('/__open-in-editor', launchMiddleware())
  },
  clientLogLevel: 'error',
  historyApiFallback: {
    rewrites: [
      { from: /.*/, to: path.posix.join(config.dev.assetsPublicPath, SKIP_LOGIN ? 'index-skip-login.html' : 'index.html') },
    ],
  },
  hot: true, // Enabling HMR
  contentBase: false, // since we use CopyWebpackPlugin.
  compress: true,
  host: HOST || config.dev.host,
  port: PORT || config.dev.port,
  open: config.dev.autoOpenBrowser,
  overlay: config.dev.errorOverlay
    ? { warnings: false, errors: true }
    : false,
  publicPath: config.dev.assetsPublicPath,
  // AI: 配置代理，并添加 CORS 处理函数
  proxy: Object.keys(config.dev.proxyTable).reduce((proxy, key) => {
    proxy[key] = {
      ...config.dev.proxyTable[key],
      // AI: 为每个代理配置添加 onProxyReq 和 onProxyRes 回调
      onProxyReq: config.dev.onProxyReq,
      onProxyRes: config.dev.onProxyRes
    }
    return proxy
  }, {}),
  quiet: false, // necessary for FriendlyErrorsPlugin
  watchOptions: {
    poll: config.dev.poll,
  },
  stats: 'errors-only', // 'errors-only' | 'minimal' | 'normal' | 'verbose'
})
