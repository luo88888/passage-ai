export default {
  requestLibPath: "import request from '@/request'",
  schemaPath: '../../../../openapi.json', // 本地快照：由后端 /api/v3/api-docs（docs 见 /api/docs）导出并去掉 /api 前缀后提交，避免重新生成依赖后端在线
  serversPath: './src',
}
