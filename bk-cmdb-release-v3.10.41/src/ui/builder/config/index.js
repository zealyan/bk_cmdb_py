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

'use strict'
// Template version: 1.3.1
// see http://vuejs-templates.github.io/webpack for documentation.

const path = require('path')
const fs = require('fs')
const parseArgs = require('minimist')

const config = {
  BUILD_TITLE: '',
  BUILD_OUTPUT: '../bin/enterprise/cmdb'
}

const argv = parseArgs(process.argv.slice(2))

process.argv.slice(2).forEach((str) => {
  const arg = str.split('=')
  if (Object.prototype.hasOwnProperty.call(config, arg[0])) {
    config[arg[0]] = arg.slice(1).join('=')
  }
})
process.CMDB_CONFIG = config
const dev = {
  // custom config
  config: Object.assign({}, config, {
    API_URL: JSON.stringify('http://localhost:9090/proxy/'),
    API_VERSION: JSON.stringify('v3'),
    API_LOGIN: JSON.stringify(''),
    AGENT_URL: JSON.stringify(''),
    AUTH_SCHEME: JSON.stringify('internal'),
    AUTH_CENTER: JSON.stringify({}),
    BUILD_VERSION: JSON.stringify('dev'),
    USER_ROLE: JSON.stringify(1),
    USER_NAME: JSON.stringify('admin'),
    FULL_TEXT_SEARCH: JSON.stringify('off'),
    USER_MANAGE: JSON.stringify(''),
    HELP_DOC_URL: JSON.stringify(''),
    DISABLE_OPERATION_STATISTIC: false
  }),

  // Paths
  assetsSubDirectory: '',
  assetsPublicPath: '/static/',
  // AI: 创建通用的代理事件处理函数，用于处理 OPTIONS 请求
  // AI: 示例: 当浏览器发送跨域POST请求前，会先发送 OPTIONS 预检请求
  onProxyRes(proxyRes, req, res) {
    // AI: 为所有代理响应添加 CORS 响应头
    res.setHeader('Access-Control-Allow-Origin', req.headers.origin || '*')
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, BK_User, HTTP_BLUEKING_SUPPLIER_ID, Cc_Request_Id')
    res.setHeader('Access-Control-Allow-Credentials', 'true')
  },
  onProxyReq(proxyReq, req, res) {
    // AI: 如果是 OPTIONS 请求，直接返回 200 而不转发到后端
    if (req.method === 'OPTIONS') {
      res.setHeader('Access-Control-Allow-Origin', req.headers.origin || '*')
      res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
      res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, BK_User, HTTP_BLUEKING_SUPPLIER_ID, Cc_Request_Id')
      res.setHeader('Access-Control-Allow-Credentials', 'true')
      res.writeHead(200)
      res.end()
      // AI: 中止原始请求，不再转发到后端
      proxyReq.abort()
    }
  },

  proxyTable: {
    '/proxy/user': {
      logLevel: 'info',
      changeOrigin: true,
      target: 'http://192.168.45.141:8083/',
      pathRewrite: {
        '^/proxy/user': '/user'
      }
    },
    '/proxy/logout': {
      logLevel: 'info',
      changeOrigin: true,
      target: 'http://192.168.45.141:8083/',
      pathRewrite: {
        '^/proxy/logout': '/logout'
      }
    },
    '/proxy/login': {
      logLevel: 'info',
      changeOrigin: true,
      target: 'http://192.168.45.141:8083/',
      pathRewrite: {
        '^/proxy/login': '/login'
      }
    },
    '/proxy': {
      logLevel: 'info',
      changeOrigin: true,
      target: 'http://192.168.45.141:8080/',
      pathRewrite: {
        '^/proxy': ''
      }
    }
  },
  // Various Dev Server settings
  host: 'localhost', // can be overwritten by process.env.HOST
  port: 9090, // can be overwritten by process.env.PORT, if port is in use, a free one will be determined
  autoOpenBrowser: true,
  errorOverlay: true,
  notifyOnErrors: true,
  poll: false, // https://webpack.js.org/configuration/dev-server/#devserver-watchoptions-

  // Use Eslint Loader?
  // If true, your code will be linted during bundling and
  // linting errors and warnings will be shown in the console.
  useEslint: true,
  // If true, eslint errors and warnings will also be shown in the error overlay
  // in the browser.
  showEslintErrorsInOverlay: true,

  /**
     * Source Maps
     */

  // https://webpack.js.org/configuration/devtool/#development
  devtool: 'cheap-module-eval-source-map',

  // If you have problems debugging vue-files in devtools,
  // set this to false - it *may* help
  // https://vue-loader.vuejs.org/en/options.html#cachebusting
  cacheBusting: true,

  cssSourceMap: true
}

const customDevConfigPath = path.resolve(__dirname, `index.dev.${argv.env || 'ee'}.js`)
const isCustomDevConfigExist = fs.existsSync(customDevConfigPath)
if (isCustomDevConfigExist) {
  const customDevConfig = require(customDevConfigPath)
  Object.assign(dev, customDevConfig)
}

module.exports = {
  dev,

  build: {
    // custom config
    config: Object.assign({}, config, {
      API_URL: '{{.site}}',
      API_VERSION: '{{.version}}',
      BUILD_VERSION: '{{.ccversion}}',
      API_LOGIN: '{{.curl}}',
      AGENT_URL: '{{.agentAppUrl}}',
      AUTH_SCHEME: '{{.authscheme}}',
      AUTH_CENTER: '{{.authCenter}}',
      USER_ROLE: '{{.role}}',
      USER_NAME: '{{.userName}}',
      FULL_TEXT_SEARCH: '{{.fullTextSearch}}',
      USER_MANAGE: '{{.userManage}}',
      HELP_DOC_URL: '{{.helpDocUrl}}',
      DISABLE_OPERATION_STATISTIC: '{{.disableOperationStatistic}}'
    }),

    // Template for index.html
    index: `${path.resolve(config.BUILD_OUTPUT)}/web/index.html`,

    // Template for login.html
    login: `${path.resolve(config.BUILD_OUTPUT)}/web/login.html`,

    // Paths
    assetsRoot: `${path.resolve(config.BUILD_OUTPUT)}/web`,

    assetsSubDirectory: '',
    assetsPublicPath: '/static/',

    /**
         * Source Maps
         */

    productionSourceMap: true,
    // https://webpack.js.org/configuration/devtool/#production
    devtool: '#source-map',

    // Gzip off by default as many popular static hosts such as
    // Surge or Netlify already gzip all static assets for you.
    // Before setting to `true`, make sure to:
    // npm install --save-dev compression-webpack-plugin
    productionGzip: false,
    productionGzipExtensions: ['js', 'css'],

    // Run the build command with an extra argument to
    // View the bundle analyzer report after build finishes:
    // `npm run build --report`
    // Set to `true` or `false` to always turn it on or off
    bundleAnalyzerReport: process.env.npm_config_report
  }
}
