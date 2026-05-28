# 代码改动清单

本文档详细记录了 BK-CMDB Python 后端开发过程中所有代码改动。

## 一、后端改动（Python）

### 1.1 配置文件改动

#### `app/config.py`

**改动说明**：添加 Skip-Login 功能配置

```python
# 添加配置项
class Config:
    # Skip Login 功能（仅开发环境使用）
    SKIP_LOGIN = os.getenv('SKIP_LOGIN', 'false').lower() == 'true'
    SKIP_LOGIN_USER = os.getenv('SKIP_LOGIN_USER', 'admin')
```

**参考**：[Go 配置参考](file:///workspace/bk-cmdb-release-v3.10.41/src/web_server/middleware/user/plugins/register/skip_login.go)

---

### 1.2 路由改动

#### `app/routes/user_routes.py`

**改动说明**：实现用户认证路由，包括 Skip-Login 逻辑

```python
@user_bp.route('/user/auth', methods=['POST'])
def user_auth():
    # Skip-Login 逻辑实现
    if Config.SKIP_LOGIN:
        # 自动返回 admin 用户 token
        skip_login_user = db.users.find_one({'username': Config.SKIP_LOGIN_USER})
        if skip_login_user:
            token = generate_token(skip_login_user['_id'])
            return make_response(data={
                'bk_token': token,
                'username': skip_login_user['username'],
                'company': skip_login_user.get('company', ''),
                'role': skip_login_user.get('role', 'dev'),
                'chinName': skip_login_user.get('chinName', '管理员')
            })
    
    # 正常登录逻辑...

@user_bp.route('/api/v3/site/config', methods=['GET'])
@user_bp.route('/site/config', methods=['GET'])
def site_config():
    # 返回站点配置
    login_version = "skip-login" if Config.SKIP_LOGIN else ""
    return make_response(data={
        "login": login_version,
        "authscheme": "internal"
    })
```

**参考**：
- [Go 登录实现](file:///workspace/bk-cmdb-release-v3.10.41/src/web_server/middleware/user/plugins/method/skip/userinfo.go)
- [Go 插件注册](file:///workspace/bk-cmdb-release-v3.10.41/src/web_server/middleware/user/plugins/register/skip_login.go)

---

### 1.3 数据模型改动

#### `app/models/db.py`

**改动说明**：实现 MongoDB 数据库初始化和模拟数据

```python
def init_mock_data():
    """初始化模拟数据到 MongoDB"""
    
    # 初始化用户数据
    users_collection = db['users']
    if users_collection.count_documents({}) == 0:
        admin_user = {
            'username': 'admin',
            'chinName': '管理员',
            'role': 'dev',
            'company': 'BlueKing',
            'phone': '400-820-5812',
            'email': 'admin@blueking.com'
        }
        users_collection.insert_one(admin_user)
    
    # 初始化业务数据、模型数据等...
```

**数据集合列表**：
- `cc_ObjectBase` - 对象模型定义
- `cc_ObjAttDes` - 对象属性定义
- `cc_ObjAttGroup` - 属性分组定义
- `cc_ObjClassification` - 对象分类定义
- `cc_ApplicationBase` - 业务数据
- `cc_PlatBase` - 云区域数据
- `users` - 用户数据
- `user_business` - 用户业务关联
- `cc_System` - 系统配置
- `auth_policies` - 权限策略

---

## 二、前端改动（UI）

### 2.1 构建配置改动

#### `builder/config/index.js`

**改动说明**：配置 API 代理到 Python 后端

```javascript
dev: {
  config: Object.assign({}, config, {
    API_URL: JSON.stringify('http://{host}:{port}/proxy/'),
  }),
  assetsPublicPath: '/',
  proxyTable: {
    '/proxy': {
      logLevel: 'info',
      changeOrigin: true,
      target: 'http://localhost:3000/',  // Python 后端地址
      pathRewrite: {
        '^/proxy': ''
      }
    }
  },
  host: '0.0.0.0',
  port: 8080,
}
```

**改动位置**：第 92-117 行

---

#### `builder/webpack/plugins.js`

**改动说明**：添加 Skip-Login HTML 模板生成

```javascript
// 添加 Skip-Login HTML 插件
const skipLoginHtmlPlugin = new HtmlWebpackPlugin({
  filename: 'index-skip-login.html',
  template: path.resolve(__dirname, '../../index.skip-login.html'),
  inject: false
})

plugins.push(skipLoginHtmlPlugin)
```

**改动位置**：第 58-63 行

---

#### `builder/webpack/devserver.js`

**改动说明**：根据环境变量切换入口页面

```javascript
const skipLogin = process.env.SKIP_LOGIN === 'true'

// 修改 historyApiFallback 配置
historyApiFallback: {
  disableDotRule: false,
  rewrites: [
    ...(skipLogin ? [{ from: /^\/.*$/, to: '/index-skip-login.html' }] : []),
    { from: /^\/.*$/, to: '/index.html' },
  ],
},
```

**改动位置**：第 8 行、第 15-21 行

---

### 2.2 新增文件

#### `index.skip-login.html`

**文件路径**：`/workspace/bk-cmdb-release-v3.10.41/src/ui/index.skip-login.html`

**功能说明**：Skip-Login 专用入口页面

**关键代码**：

```html
<script type="text/javascript">
    // 动态获取当前协议和端口
    var protocol = window.location.protocol
    var host = window.location.hostname
    var port = window.location.port || (protocol === 'https:' ? '443' : '80')
    var baseUrl = protocol + '//' + host + (port ? ':' + port : '')
    
    window.Site = {
        url: baseUrl + "/proxy/",
        version: "v3",
        login: "skip-login",  // 关键：标识 Skip-Login 模式
        agent: "",
        authscheme: "internal",
        buildVersion: "dev",
        fullTextSearch: "off",
        helpDocUrl: null,
        disableOperationStatistic: false
    }
    window.API_HOST = baseUrl + "/proxy/"
    window.API_PREFIX = API_HOST + 'api/' + Site.version
</script>

<!-- 自动登录脚本 -->
<script type="text/javascript">
    (async function() {
        try {
            const response = await fetch(window.API_HOST + 'user/auth', {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            const result = await response.json()
            if (result.result) {
                document.cookie = 'bk_token=' + result.data.bk_token + ';path=/'
                console.log('[Skip-Login] 登录成功')
            }
        } catch (error) {
            console.error('[Skip-Login] 登录失败:', error)
        }
    })()
</script>
```

---

#### `src/setup/vconsole.js`

**文件路径**：`/workspace/bk-cmdb-release-v3.10.41/src/ui/src/setup/vconsole.js`

**功能说明**：vConsole 移动端调试工具配置

```javascript
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
```

---

### 2.3 源代码改动

#### `src/main.js`

**改动说明**：导入 vConsole 初始化模块

```javascript
import './setup/vcookie'
import './setup/permission'
import './setup/build-in-vars'
import './setup/vconsole'  // 新增：vConsole 初始化
import '@/assets/icon/bk-icon-cmdb/style.css'
```

**改动位置**：第 28 行

---

#### `src/api/index.js`

**改动说明**：动态使用 window.API_PREFIX 作为 baseURL

```javascript
// axios实例
const axiosInstance = Axios.create({
  baseURL: window.API_PREFIX || 'http://localhost:9090/proxy/api/v3',  // 改为动态获取
  xsrfCookieName: 'data_csrftoken',
  xsrfHeaderName: 'X-CSRFToken',
  withCredentials: true
})
```

**改动位置**：第 15 行

---

#### `src/store/modules/api/object-biz.js`

**改动说明**：添加 transformData: false 配置

```javascript
getAuthorizedBusiness({ commit, state }, config = {}) {
  return $http.get('biz/with_reduced?sort=bk_biz_id', {
    ...config,
    transformData: false  // 新增：确保获得完整响应对象
  })
},
```

**改动位置**：第 10 行

---

## 三、依赖包改动

### 3.1 Python 依赖

**新增依赖**：

```bash
pip install flask flask-cors pymongo bcrypt Flask-Session
```

**依赖说明**：
- `flask` - Web 框架
- `flask-cors` - 跨域支持
- `pymongo` - MongoDB 驱动
- `bcrypt` - 密码加密
- `Flask-Session` - Session 管理

---

### 3.2 Node.js 依赖

**新增依赖**：

```bash
npm install vconsole --save
```

**依赖说明**：
- `vconsole` - 移动端调试工具

---

## 四、配置文件改动

### 4.1 环境变量

**新增环境变量**：

```bash
# Skip-Login 功能开关
export SKIP_LOGIN=true

# Skip-Login 自动登录用户（可选，默认为 admin）
export SKIP_LOGIN_USER=admin
```

**配置文件位置**：
- Python 后端：`app/config.py`
- 前端启动：`npm run dev` 时设置 `SKIP_LOGIN=true`

---

## 五、数据初始化

### 5.1 MongoDB 数据集合

**初始化的数据集合**：

| 集合名称 | 数据类型 | 说明 |
|---------|---------|------|
| `users` | 用户 | 包含 admin 用户 |
| `cc_ObjectBase` | 模型 | 对象模型定义 |
| `cc_ObjAttDes` | 属性 | 对象属性定义 |
| `cc_ObjAttGroup` | 分组 | 属性分组定义 |
| `cc_ObjClassification` | 分类 | 对象分类定义 |
| `cc_ApplicationBase` | 业务 | 业务数据 |
| `cc_PlatBase` | 区域 | 云区域数据 |
| `user_business` | 关联 | 用户业务关联 |
| `cc_System` | 系统 | 系统配置 |
| `auth_policies` | 权限 | 权限策略 |

---

## 六、安全注意事项

### 6.1 Skip-Login 安全提示

⚠️ **重要提醒**：

1. **禁止在生产环境启用** - Skip-Login 会绕过所有身份验证
2. **仅本地开发使用** - 确保在安全的开发环境中使用
3. **环境变量隔离** - 确保生产环境不设置 `SKIP_LOGIN=true`
4. **定期清理** - 开发和测试完成后，及时禁用 Skip-Login 功能

### 6.2 生产环境检查清单

- [ ] 移除所有 `SKIP_LOGIN=true` 环境变量
- [ ] 确保后端配置文件中 `Config.SKIP_LOGIN = False`
- [ ] 验证正常登录流程可用
- [ ] 检查所有 API 都需要有效 Token
- [ ] 移除测试用户或设置强密码

---

## 七、测试验证

### 7.1 后端测试

```bash
# 测试 Skip-Login 配置
curl http://localhost:3000/site/config
# 预期输出: {"data":{"authscheme":"internal","login":"skip-login"},"result":true}

# 测试用户认证
curl -X POST http://localhost:3000/user/auth \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'
# 预期输出: 包含 bk_token 的成功响应
```

### 7.2 前端测试

```bash
# 启动前端开发服务器
cd /workspace/bk-cmdb-release-v3.10.41/src/ui
export SKIP_LOGIN=true
npm run dev

# 访问应用
# http://localhost:8080
# 应该自动以 admin 用户登录
```

### 7.3 vConsole 测试

```bash
# 在浏览器控制台检查
window.vConsole

# 应该输出 VConsole 实例
# 页面右下角应显示 vConsole 按钮
```

---

## 八、回滚方案

### 8.1 回滚 Skip-Login 功能

1. **后端回滚**：
   - 将 `app/config.py` 中的 `SKIP_LOGIN` 改为 `False`
   - 移除 `app/routes/user_routes.py` 中的 Skip-Login 相关代码

2. **前端回滚**：
   - 删除 `index.skip-login.html` 文件
   - 移除 `builder/webpack/plugins.js` 中的 Skip-Login 插件
   - 移除 `builder/webpack/devserver.js` 中的条件判断
   - 移除 `src/main.js` 中的 vconsole 导入

3. **恢复代理配置**：
   - 将 `builder/config/index.js` 中的 proxyTable.target 改回原地址

### 8.2 依赖回滚

```bash
# Python 依赖
pip uninstall flask flask-cors pymongo bcrypt Flask-Session

# Node.js 依赖
npm uninstall vconsole
```

---

## 九、相关文档

- [UI 开发环境指南](file:///workspace/docs/ui_dev_guide.md)
- [MongoDB 安装指南](file:///workspace/docs/mongodb_install.md)
- [Skip-Login 原理分析](file:///workspace/docs/skip_login_analysis.md)
- [Go 后端 Skip-Login 实现](file:///workspace/bk-cmdb-release-v3.10.41/src/web_server/middleware/user/plugins/register/skip_login.go)

---

## 十、版本历史

| 日期 | 版本 | 改动内容 | 作者 |
|------|------|---------|------|
| 2026-05-28 | v1.0 | 初始版本，实现 Skip-Login 功能和 vConsole | AI Assistant |
