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

import { getAuthorizedBusiness, getAuthorizedBusinessSet } from '@/router/business-interceptor.js'
import { verifyAuth } from '@/services/auth.js'
import store from '@/store'

const preloadConfig = {
  fromCache: false,
  cancelWhenRouteChange: false
}

export function getClassifications(app) {
  return app.$store.dispatch('objectModelClassify/searchClassificationsObjects', {
    params: {},
    config: {
      ...preloadConfig,
      requestId: 'post_searchClassificationsObjects'
    }
  })
}

export function getUserCustom(app) {
  return app.$store.dispatch('userCustom/searchUsercustom', {
    config: {
      ...preloadConfig,
      fromCache: false,
      requestId: 'post_searchUsercustom'
    }
  })
}

export function getGlobalUsercustom(app) {
  return app.$store.dispatch('userCustom/getGlobalUsercustom', {
    config: {
      ...preloadConfig,
      fromCache: false,
      globalError: false
    }
  }).catch(() => ({}))
}

/**
 * 初始化全局配置
 * @param {Object} app Vue 应用实例
 * @returns
 */
export async function getGlobalConfig(app) {
  return app.$store.dispatch('globalConfig/fetchConfig', {
    config: {
      ...preloadConfig,
      fromCache: false,
      globalError: false
    }
  })
}

/**
 * 验证平台管理模块的权限
 */
export const verifyPlatformManagementAuth = async () => {
  const [{ is_pass: isPass }] = await verifyAuth([{
    action: 'update',
    resource_type: 'configAdmin'
  }])

  if (isPass) {
    store.commit('globalConfig/setAuth', isPass)
  }
}

/**
 * 获取主线模型，数据会写入store
 */
const getMainLineModels = async () => {
  store.dispatch('objectMainLineModule/searchMainlineObject', {
    config: {
      ...preloadConfig,
      requestId: 'getMainLineModels'
    }
  })
}

export default async function (app) {
  console.log('[PRELOAD] 开始预加载...')

  // 首先尝试自动登录
  try {
    // 先尝试获取用户信息
    console.log('[PRELOAD] 尝试获取用户信息...')
    const userInfoResult = await app.$http.get('user/info', {
      transformData: false,
      globalError: false
    })

    if (userInfoResult && userInfoResult.result && userInfoResult.data) {
      const userInfo = {
        name: userInfoResult.data.username,
        admin: userInfoResult.data.admin ? '1' : '0',
        display_name: userInfoResult.data.display_name
      }
      window.User = userInfo
      app.$store.dispatch('login', userInfo)
      console.log('[PRELOAD] 用户会话已恢复')
    }
  } catch (e) {
    console.log('[PRELOAD] 获取用户信息失败，尝试登录...')
    try {
      // 如果用户信息获取失败，尝试登录
      const loginResult = await app.$http.post('user/auth', {}, {
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
        console.log('[PRELOAD] 自动登录成功')
      }
    } catch (loginErr) {
      console.error('[PRELOAD] 自动登录失败:', loginErr)
    }
  }

  if (window.Site.authscheme === 'iam') {
    verifyPlatformManagementAuth()
  } else {
    // 开源版的可能没有 IAM，不需要鉴权
    store.commit('globalConfig/setAuth', true)
  }

  // 获取有访问权限的业务
  getAuthorizedBusiness()

  // 获取有访问权限的业务集
  getAuthorizedBusinessSet()

  getMainLineModels()

  return Promise.all([
    getGlobalConfig(app),
    getClassifications(app),
    getUserCustom(app),
    getGlobalUsercustom(app)
  ])
}
