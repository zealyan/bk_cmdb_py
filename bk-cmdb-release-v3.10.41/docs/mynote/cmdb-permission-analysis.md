# CMDB 权限系统分析报告

## 问题分析

### 1. 权限系统架构
- **核心组件**：CMDB有独立的`auth_server`服务负责权限管理
- **控制机制**：通过`EnableAuthorize()`函数控制权限系统的启用/禁用
- **授权逻辑**：当权限系统禁用时，所有请求自动授权通过
- **集成方案**：支持与蓝鲸IAM权限中心集成

### 2. 业务权限检查逻辑
- **检查机制**：当权限系统启用时，通过`AuthorizeByBusinessID`函数验证用户权限
- **无权限触发**：当验证失败返回`NoAuthorizeError`时，会显示"暂无该业务权限或业务不存在"的提示
- **错误码**：与权限相关的错误码包括1100001-1100004

### 3. 用户选择功能
- **模式支持**：支持三种用户管理模式：
  - `BlueKing`：通过ESB接口获取用户数据
  - `OpenSource`：从配置文件获取用户数据
  - `Skip`：直接返回admin用户
- **问题原因**：用户选择器无法获取后端用户数据，可能是因为配置模式不正确或接口调用失败

### 4. CMDB内部用户管理
- **用户存储**：在`OpenSource`模式下，用户信息存储在配置文件中，格式为`user:password`
- **权限配置**：只有管理员有权限进行权限配置
- **admin用户**：默认拥有所有权限

## 解决方案

### 1. 解决业务权限问题
- **检查权限配置**：确认`auth_enabled`配置是否正确，如需禁用权限系统，设置为`false`
- **验证admin权限**：确保admin用户在OpenSource模式下正确配置
- **权限系统禁用**：如果不需要IAM集成，建议禁用权限系统以避免无权限提示

### 2. 解决用户选择功能
- **配置模式检查**：确认当前使用的用户管理模式，建议使用`OpenSource`模式
- **用户配置**：在配置文件中正确配置用户信息，格式为`user:password`
- **接口修复**：确保`/proxy/user/list`接口能够正确返回用户数据

### 3. 内部用户管理方案
- **配置文件**：在`common.yaml`中配置`webServer.session.userInfo`，格式为`user1:pass1,user2:pass2`
- **admin用户**：确保admin用户存在于配置中，以获得所有权限
- **权限控制**：使用admin用户进行权限配置和管理

## 实施建议
1. **修改配置**：在部署时设置`--auth_enabled false`以禁用权限系统
2. **用户配置**：在`common.yaml`中添加用户配置
3. **测试验证**：验证admin用户能正常访问业务，用户选择器能显示用户数据
4. **文档更新**：记录权限系统的配置和使用方法

## 技术细节

### 权限检查核心代码
- **权限控制**：`src/common/auth/auth.go`中的`EnableAuthorize()`函数
- **业务权限检查**：`src/ac/extensions/business.go`中的`AuthorizeByBusinessID`函数
- **用户管理**：`src/web_server/middleware/user/plugins/method/opensource/userinfo.go`中的`GetUserList`方法

### 配置参数
- **权限系统开关**：`--auth_enabled`（true/false）
- **用户信息配置**：`webServer.session.userInfo`
- **认证模式**：`--auth_scheme`（internal/blueking）

## 实施步骤

### 1. 修改用户配置

编辑 `/home/cmdb/cmdb/cmdb_adminserver/configures/common.yaml` 文件，更新 `userInfo` 配置：

```bash
# 查看当前配置
cat /home/cmdb/cmdb/cmdb_adminserver/configures/common.yaml | grep 'userInfo'

# 修改用户配置，添加admin、tom、jelly三个用户
sed -i 's/userInfo: admin:admin/userInfo: admin:admin,tom:tom123,jelly:jelly123/g' /home/cmdb/cmdb/cmdb_adminserver/configures/common.yaml

# 验证修改结果
cat /home/cmdb/cmdb/cmdb_adminserver/configures/common.yaml | grep 'userInfo'
```

### 2. 确认权限配置

确保以下配置正确：

```yaml
# common.yaml 中的关键配置
webServer:
  session:
    userInfo: admin:admin,tom:tom123,jelly:jelly123
  app:
    authscheme: internal  # 使用内部权限模式
  login:
    version: opensource   # 使用开源登录模式
```

### 3. 确认服务启动参数

检查各服务的启动脚本，确保 `--enable-auth=false`：

```bash
# 查看adminserver启动脚本
cat /home/cmdb/cmdb/cmdb_adminserver/start.sh

# 应该包含 --enable-auth=false 参数
```

### 4. 刷新配置到配置中心

```bash
cd /home/cmdb/cmdb
./refresh_config.sh all
```

### 5. 重启服务（如需要）

如果配置未生效，可以重启相关服务：

```bash
cd /home/cmdb/cmdb
./stop.sh
./start.sh
```

### 6. 验证服务状态

```bash
# 检查所有CMDB服务是否正常运行
ps -ef | grep cmdb_ | grep -v grep
```

## 配置验证

### 用户列表验证

配置完成后，可以通过以下方式验证用户列表：

```bash
# 测试用户列表接口
curl "http://192.168.45.141:8083/user/list"
```

预期返回包含三个用户：admin、tom、jelly

### 登录验证

使用以下账号密码登录CMDB：

| 用户名 | 密码 | 权限说明 |
|--------|------|----------|
| admin | admin | 管理员，拥有所有权限 |
| tom | tom123 | 普通用户 |
| jelly | jelly123 | 普通用户 |

## 注意事项

1. **权限系统已禁用**：所有服务都以 `--enable-auth=false` 启动，不会进行IAM权限验证
2. **用户数据存储**：用户信息存储在配置文件中，不依赖外部用户中心
3. **业务访问**：由于权限系统禁用，所有用户都可以正常访问业务，不会出现"无业务权限"提示
4. **配置持久化**：修改后的配置已通过 `refresh_config.sh` 刷新到配置中心（ZooKeeper）

## 结论

通过以上分析和解决方案，您可以在不使用外部用户中心或IAM的情况下，使用CMDB内部的用户配置和权限方案解决当前的权限问题。建议在开发环境中禁用权限系统，以简化开发和测试过程。

当前配置已完成：
- ✅ 用户配置：admin:admin, tom:tom123, jelly:jelly123
- ✅ 权限模式：internal（内部模式）
- ✅ 登录模式：opensource（开源模式）
- ✅ 权限系统：已禁用（--enable-auth=false）
- ✅ 配置刷新：已完成
- ✅ 服务状态：所有服务正常运行