# BK-CMDB 原Go代码 Skip认证逻辑分析

## 一、概述

Skip认证是BK-CMDB为开发环境提供的一种快速登录机制，允许开发者无需输入用户名密码即可直接以admin身份登录系统。

## 二、插件注册机制

### 2.1 插件导入

在 `src/web_server/middleware/user/plugins/register/skip_login.go` 中注册插件：

```go
package manager

import (
    // import skip login plugin
    _ "configcenter/src/web_server/middleware/user/plugins/method/skip"
)
```

通过Go的匿名导入机制，在程序启动时自动执行 `skip` 包的 `init()` 函数，完成插件注册。

### 2.2 插件定义

在 `src/web_server/middleware/user/plugins/method/skip/userinfo.go` 中：

```go
func init() {
    plugin := &metadata.LoginPluginInfo{
        Name:       "skip login system",
        Version:    common.BKSkipLoginPluginVersion,
        HandleFunc: &user{},
    }
    manager.RegisterPlugin(plugin)
}
```

## 三、核心登录逻辑

### 3.1 LoginUser 方法

Skip认证的核心实现直接返回默认的admin用户信息：

```go
func (m *user) LoginUser(c *gin.Context, config map[string]string, isMultiOwner bool) (user *metadata.LoginUserInfo, loginSucc bool) {

    session := sessions.Default(c)

    cookieOwnerID, err := c.Cookie(common.BKHTTPOwnerID)
    if "" == cookieOwnerID || nil != err {
        c.SetCookie(common.BKHTTPOwnerID, common.BKDefaultOwnerID, 0, "/", "", false, false)
        session.Set(common.WEBSessionOwnerUinKey, cookieOwnerID)
    } else if cookieOwnerID != session.Get(common.WEBSessionOwnerUinKey) {
        session.Set(common.WEBSessionOwnerUinKey, cookieOwnerID)
    }

    user = &metadata.LoginUserInfo{
        UserName: "admin",
        ChName:   "admin",
        Phone:    "",
        Email:    "blueking",
        Role:     "",
        BkToken:  "",
        OnwerUin: "0",
        IsOwner:  false,
        Language: webCommon.GetLanguageByHTTPRequest(c),
    }
    return user, true
}
```

### 3.2 主要特点

1. **无密码验证**：跳过所有用户名密码验证逻辑
2. **固定用户信息**：直接返回admin用户
3. **Cookie管理**：处理 `BKHTTPOwnerID` cookie，设置默认值为 `0`
4. **Session同步**：确保session中的owner信息与cookie一致

### 3.3 返回的用户信息

| 字段 | 值 | 说明 |
|------|-----|------|
| UserName | "admin" | 用户名 |
| ChName | "admin" | 中文名 |
| Phone | "" | 电话（空） |
| Email | "blueking" | 邮箱 |
| Role | "" | 角色（空） |
| BkToken | "" | Token（空） |
| OnwerUin | "0" | 所有者ID |
| IsOwner | false | 是否所有者 |
| Language | 从请求获取 | 语言设置 |

## 四、支持的登录版本

BK-CMDB支持多种登录方式，通过 `webServer.login.version` 配置项切换：

| 版本值 | 说明 | 使用场景 |
|--------|------|----------|
| `skip-login` | 免登录模式，直接使用admin账号 | 开发环境、测试环境 |
| `blueking` | 使用蓝鲸PaaS平台登录 | 正式环境（接入蓝鲸平台） |
| `opensource` | 开源版登录（用户名密码） | 正式环境（开源部署） |

### 4.1 配置位置

在配置文件（config.yaml）中的位置：

```yaml
webServer:
  login:
    # 使用的登录系统
    version: skip-login
```

### 4.2 版本标识常量

在 `src/common/definitions.go` 中定义版本常量：

```go
// 登录版本常量定义
BKBluekingLoginPluginVersion = "blueking"    // 蓝鲸登录
BKOpenSourceLoginPluginVersion = "opensource" // 开源版登录
BKSkipLoginPluginVersion = "skip-login"       // 免登录
```

### 4.3 代码引用位置

- **配置读取**：`src/web_server/app/server.go:152`
  ```go
  w.Config.LoginVersion, _ = cc.String("webServer.login.version")
  ```
- **插件选择**：`src/web_server/middleware/user/public.go:50`
  ```go
  user := plugins.CurrentPlugin(c, m.config.LoginVersion)
  ```

## 五、核心登录逻辑

### 5.1 配置触发

在配置文件中设置：
```yaml
webServer:
  login:
    version: "skip-login"
```

### 5.2 执行流程

1. 系统启动时，`skip` 包被导入，自动执行 `init()` 函数注册插件
2. 用户请求到达时，中间件调用 `plugins.CurrentPlugin(c, config.LoginVersion)` 获取当前登录插件
3. 当 `LoginVersion` 为 `skip-login` 时，使用skip插件
4. 调用 `user.LoginUser()` 方法，直接返回admin用户信息
5. 将用户信息写入session，完成登录
6. 后续请求都会自动通过认证，无需再次验证

## 六、其他接口实现

### 6.1 GetLoginUrl

```go
func (m *user) GetLoginUrl(c *gin.Context, config map[string]string, input *metadata.LogoutRequestParams) string {
    // 返回配置的登录URL
    // Skip模式下通常返回空或重定向到首页
}
```

### 6.2 GetUserList

```go
func (m *user) GetUserList(c *gin.Context, config map[string]string) ([]*metadata.LoginSystemUserInfo, *errors.RawErrorInfo) {
    return []*metadata.LoginSystemUserInfo{
        {
            CnName: "admin",
            EnName: "admin",
        },
    }, nil
}
```

## 七、安全注意事项

**⚠️ 重要提醒**：
- Skip Login仅用于开发环境
- 生产环境必须关闭此功能
- 启用后会绕过所有身份验证机制
- 所有请求都会以admin身份执行

## 八、适用场景

- 本地开发调试
- 自动化测试环境
- 演示环境
- 快速原型验证
