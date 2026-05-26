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

import Vue from 'vue'
import VConsole from 'vconsole'
import App from './App.vue'
import router from './router/index.js'
import store from './store'
import i18n from './i18n'
import cmdbRequestMixin from './mixins/request'
import cmdbAuthMixin from './mixins/auth'
import cmdbAppMixin from './mixins/app.js'
import cmdbFormatter from './filters/formatter.js'
import cmdbUnitFilter from './filters/unit.js'
import cmdbUI from './components/ui'
import cmdbSearchComponent from './components/search/index'
import routerActions from './router/actions'
import tools from './utils/tools'
import clipboard from 'vue-clipboard2'
import './magicbox'
import './directives'
import api from './api'
import './setup/cookie'
import './setup/permission'
import './setup/build-in-vars'
import '@/assets/icon/bk-icon-cmdb/style.css'
import '@icon-cool/bk-icon-cmdb-colorful/src/index'
import './assets/scss/common.scss'

new VConsole()

Vue.use(cmdbUI)
Vue.use(cmdbSearchComponent)
Vue.use(clipboard)
Vue.mixin(cmdbRequestMixin)
Vue.mixin(cmdbAuthMixin)
Vue.mixin(cmdbAppMixin)
Vue.filter('formatter', cmdbFormatter)
Vue.filter('unit', cmdbUnitFilter)
Vue.prototype.$http = api
Vue.prototype.$tools = tools
Vue.prototype.$routerActions = routerActions
/* eslint-disable no-new */
const app = new Vue({
  el: '#app',
  router,
  store,
  i18n,
  components: { App },
  template: '<App/>'
})

window.CMDB_APP = app

async function initUserSession() {
  if (window.User) {
    return
  }

  try {
    // 首先尝试获取用户信息
    const result = await api.get('user/info', {
      transformData: false,
      globalError: false
    })

    if (result && result.result && result.data) {
      const userInfo = {
        name: result.data.username,
        admin: result.data.admin ? '1' : '0',
        display_name: result.data.display_name
      }
      window.User = userInfo
      app.$store.dispatch('login', userInfo)
      console.debug('User session restored:', userInfo)
      return
    }
  } catch (error) {
    console.debug('No active session found, trying auto-login')
  }

  // 如果没有会话，尝试自动登录
  try {
    const loginResult = await api.post('user/auth', {}, {
      transformData: false,
      globalError: false
    })

    if (loginResult && loginResult.result && loginResult.data) {
      const userInfo = {
        name: loginResult.data.username,
        admin: '1',
        display_name: loginResult.data.display_name
      }
      window.User = userInfo
      app.$store.dispatch('login', userInfo)
      console.debug('Auto-login successful:', userInfo)
    }
  } catch (error) {
    console.debug('Auto-login failed:', error)
  }
}

initUserSession()

if (process.env.COMMIT_ID) {
  window.CMDB_COMMIT_ID = process.env.COMMIT_ID
}
