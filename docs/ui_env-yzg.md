# UI开发环境准备与运行指南

## 1. 环境要求

### 1.1 Node.js 环境
- **Node.js 版本**: v14.21.3
- **安装路径**: `E:\node-v14.21.3-win-x64`
- **本地依赖路径**:  `E:\workspace_webstorm\bk-cmdb-v3.10.41\bk-cmdb-release-v3.10.41\src\ui\node_modules`
## 项目结构
- **项目根目录**: `E:\workspace_webstorm\bk-cmdb-v3.10.41\bk-cmdb-release-v3.10.41\src\ui`
## Build Setup

``` bash
# install dependencies
npm install

# set dev config -- API_URL in 'builder/config/index.js'
# the API_URL is the address of apiServer and it should start with 'http(s)://', end with '/'
# serve with hot reload at localhost:9090
npm run dev

# build for production with minification
npm run build

# build for production and view the bundle analyzer report
npm run build --report
```