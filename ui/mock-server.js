const http = require('http')
const crypto = require('crypto')

const generateResponse = (data = []) => ({
  result: true,
  code: 0,
  message: 'success',
  data
})

const generatePageResponse = (list = [], count = 0) => ({
  result: true,
  code: 0,
  message: 'success',
  data: {
    count,
    info: list
  }
})

const mockData = {
  biz: [
    { bk_biz_id: 1, bk_biz_name: '测试业务', description: '用于测试的业务' }
  ],
  hosts: [
    { bk_host_id: 1, bk_host_innerip: '192.168.1.100', bk_cloud_id: 0, bk_biz_id: 1 },
    { bk_host_id: 2, bk_host_innerip: '192.168.1.101', bk_cloud_id: 0, bk_biz_id: 1 },
    { bk_host_id: 3, bk_host_innerip: '192.168.1.102', bk_cloud_id: 0, bk_biz_id: 1 }
  ],
  modules: [
    { bk_module_id: 1, bk_module_name: '数据库', bk_set_id: 1, bk_biz_id: 1 },
    { bk_module_id: 2, bk_module_name: '应用', bk_set_id: 1, bk_biz_id: 1 },
    { bk_module_id: 3, bk_module_name: 'web', bk_set_id: 1, bk_biz_id: 1 }
  ],
  sets: [
    { bk_set_id: 1, bk_set_name: '集群1', bk_biz_id: 1 },
    { bk_set_id: 2, bk_set_name: '集群2', bk_biz_id: 1 }
  ]
}

const handleRequest = (req, res) => {
  const url = req.url.split('?')[0]
  const method = req.method

  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, X-Requested-With')

  if (method === 'OPTIONS') {
    res.writeHead(200)
    res.end()
    return
  }

  let body = ''
  req.on('data', chunk => {
    body += chunk.toString()
  })

  req.on('end', () => {
    let responseData = { result: true, code: 0, message: 'success', data: {} }

    if (url.startsWith('/api/v3/biz/search')) {
      responseData = generatePageResponse(mockData.biz, mockData.biz.length)
    } else if (url.startsWith('/api/v3/hosts/search')) {
      responseData = generatePageResponse(mockData.hosts, mockData.hosts.length)
    } else if (url.startsWith('/api/v3/modules/search')) {
      responseData = generatePageResponse(mockData.modules, mockData.modules.length)
    } else if (url.startsWith('/api/v3/sets/search')) {
      responseData = generatePageResponse(mockData.sets, mockData.sets.length)
    } else if (url.includes('/object/v3/')) {
      responseData = generateResponse({})
    } else if (url.includes('/topo/v3/')) {
      responseData = generateResponse({})
    } else if (url.includes('/find/objectassociation')) {
      responseData = generateResponse([])
    } else {
      responseData = generateResponse({})
    }

    res.writeHead(200, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify(responseData))
  })
}

const server = http.createServer(handleRequest)
const PORT = 8080

server.listen(PORT, () => {
  console.log(`Mock API Server running at http://localhost:${PORT}/`)
  console.log('Endpoints:')
  console.log('  - GET /api/v3/biz/search')
  console.log('  - GET /api/v3/hosts/search')
  console.log('  - GET /api/v3/modules/search')
  console.log('  - GET /api/v3/sets/search')
})
