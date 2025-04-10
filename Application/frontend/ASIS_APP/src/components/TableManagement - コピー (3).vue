<!-- 保留模板部分不变 -->
<template>
  <div class="command-management-container">
    <!-- 查询表单区域 -->
    <div class="query-section">
      <el-form :model="queryParams" inline>
        <el-form-item label="命令类型">
          <el-select 
            v-model="queryParams.command_type" 
            clearable
            placeholder="请选择命令类型"
          >
            <el-option
              v-for="type in commandTypes"
              :key="type.value"
              :label="type.label"
              :value="type.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="日期范围">
          <el-date-picker
            v-model="queryParams.date_range"
            type="daterange"
            value-format="YYYY-MM-DD"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
          />
        </el-form-item>

        <el-form-item label="关键词">
          <el-input
            v-model="queryParams.search_key"
            placeholder="命令内容/表格数据"
            clearable
            @keyup.enter="handleSearch"
          >
            <template #append>
              <el-button @click="handleSearch">
                <el-icon><Search /></el-icon>
              </el-button>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>
            <span>查询</span>
          </el-button>
          <el-button type="success" @click="handleCreateCommand">
            <el-icon><Plus /></el-icon>
            <span>新建命令</span>
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 命令列表区域 -->
    <div class="command-list-section">
      <el-table
        :data="groupedCommands"
        v-loading="loading"
        row-key="command_value"
        stripe
        highlight-current-row
        style="width: 100%"
      >
        <!-- 命令类型列 -->
        <el-table-column prop="command_type" label="类型" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="getCommandTypeStyle(row.command_type)" effect="light">
              {{ row.command_type }}
            </el-tag>
          </template>
        </el-table-column>

        <!-- 命令内容列 -->
        <el-table-column prop="command_value" label="命令内容" min-width="200" show-overflow-tooltip />

        <!-- 展开文件夹 -->
        <el-table-column type="expand">
          <template #default="{ row }">
            <el-table
              :data="Object.values(row.folders)"
              row-key="out_folder_path"
              style="width: 100%"
            >
              <el-table-column prop="out_folder_path" label="存储目录" width="350">
                <template #default="{ row }">
                  <el-link 
                    type="primary" 
                    @click.stop="previewFolder(row.out_folder_path)"
                  >
                    {{ row.out_folder_path }}
                  </el-link>
                </template>
              </el-table-column>

              <!-- 展开文件 -->
              <el-table-column type="expand">
                <template #default="{ row }">
                  <div class="file-content-section">
                    <div class="path-list-header">
                      <el-icon><Document /></el-icon>
                      <span>关联文件列表 (按时间倒序)</span>
                    </div>
                    
                    <div class="path-list-container">
                      <div 
                        v-for="(file, index) in row.files" 
                        :key="index"
                        class="path-item"
                      >
                        <div class="path-header">
                          <el-icon :class="{'rotate-icon': showFileEditor && currentFile?.path === file.full_path}">
                            <ArrowRight />
                          </el-icon>
                          <el-link 
                            type="primary" 
                            @click.stop="() => toggleFileEditor(file, file.full_path)"
                            style="margin-left: 20px;"
                          >
                            {{ file.file_name }}
                          </el-link>
                          <span class="file-time">{{ formatDateTime(file.created_at) }}</span>
                          <el-button 
                            type="info" 
                            size="small" 
                            @click.stop="previewMarkdown(file.full_path)"
                            style="margin-left: 10px;"
                          >
                            <el-icon><View /></el-icon>
                            <span>预览</span>
                          </el-button>
                          <el-button 
                            type="primary" 
                            size="small" 
                            @click.stop="() => file.full_path && callDifyAgent(file, file.full_path)"
                            :loading="callingAgent"
                            style="margin-left: 10px;"
                          >
                            <el-icon><MagicStick /></el-icon>
                            <span>调用智能体</span>
                          </el-button>
                        </div>

                        <div class="file-editor-container" v-if="showFileEditor && currentFile?.path === file.full_path">
                          <div class="editor-area">
                            <el-input
                              v-model="fileContent"
                              type="textarea"
                              :rows="20"
                              resize="none"
                              placeholder="Markdown内容..."
                              @input="handleContentChange"
                            />
                          </div>
                          <div class="preview-area">
                            <div class="preview-header">
                              <span>实时预览</span>
                              <div>
                                <el-tag v-if="unsavedChanges" type="warning">未保存</el-tag>
                                <span class="last-saved" v-if="lastSavedTime">
                                  最后修改: {{ formatDateTime(lastSavedTime) }}
                                </span>
                              </div>
                            </div>
                            <div class="markdown-preview" v-html="compiledMarkdown" />
                          </div>
                          
                          <div class="editor-actions">
                            <el-button 
                              type="primary" 
                              @click="saveFileContent(file, file.full_path)"
                              :loading="savingFile"
                              :disabled="!unsavedChanges"
                            >
                              <el-icon><Upload /></el-icon>
                              <span>保存更改</span>
                            </el-button>
                            <el-button @click="reloadFileContent(file.full_path)">
                              <el-icon><Refresh /></el-icon>
                              <span>重新加载</span>
                            </el-button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </template>
              </el-table-column>
            </el-table>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 分页区域 -->
    <div class="pagination-section">
      <el-pagination
        v-model="pagination.current_page"
        :page-size="pagination.page_size"
        @size-change="handleSizeChange"
        :total="pagination.total"
        @current-change="handlePageChange"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        background
      />
    </div>

    <!-- 命令编辑对话框 -->
    <el-dialog
      v-model="commandDialogVisible"
      :title="dialogTitle"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form 
        :model="editingCommand" 
        label-width="100px"
        ref="commandFormRef"
        :rules="commandRules"
      >
        <el-form-item label="命令类型" prop="command_type">
          <el-select 
            v-model="editingCommand.command_type" 
            placeholder="请选择命令类型"
          >
            <el-option
              v-for="type in commandTypes"
              :key="type.value"
              :label="type.label"
              :value="type.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="命令内容" prop="command_value">
          <el-input 
            v-model="editingCommand.command_value" 
            type="textarea" 
            rows="4"
            placeholder="请输入命令内容"
            show-word-limit
            maxlength="500"
          />
        </el-form-item>
        
        <el-form-item 
          label="表格文件路径" 
          prop="table_data_path"
          v-if="isCreating"
        >
          <el-input
            v-model="editingCommand.table_data_path"
            placeholder="输入Markdown文件路径，如：F:\path\to\file.md"
          />
          <div class="path-hint">
            <el-icon><InfoFilled /></el-icon>
            请确保路径可访问且有写入权限
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="commandDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveCommand">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Search, Plus, Document, Delete, View, 
  Upload, InfoFilled, ArrowRight, Refresh, MagicStick, Files 
} from '@element-plus/icons-vue'
import { marked } from 'marked'
import hljs from 'highlight.js'
import dayjs from 'dayjs'

// 配置marked
marked.setOptions({
  breaks: true,
  gfm: true,
  highlight: (code, lang) => {
    const language = hljs.getLanguage(lang) ? lang : 'plaintext'
    return hljs.highlight(code, { language }).value
  }
})

// 状态管理
const loading = ref(false)
const savingFile = ref(false)
const commandDialogVisible = ref(false)
const isCreating = ref(false)
const commandFormRef = ref(null)
const showFileEditor = ref(false)
const fileContent = ref('')
const lastSavedTime = ref(null)
const unsavedChanges = ref(false)
const fileStatus = ref({})
const currentFile = ref(null)
const callingAgent = ref(false)
const currentCallingFile = ref(null)

// 数据相关
const commandList = ref([])
const currentCommand = ref(null)

// 查询参数
const queryParams = reactive({
  command_type: '',
  date_range: [],
  search_key: ''
})

// 分页参数
const pagination = reactive({
  current_page: 1,
  page_size: 10,
  total: 0
})

// 编辑中的命令
const editingCommand = reactive({
  id: null,
  command_value: '',
  command_type: 'CLP',
  table_data_path: ''
})

// 命令类型选项
const commandTypes = [
  { value: 'CLP', label: 'CLP命令' },
  { value: 'RPGLE', label: 'RPG程序' },
  { value: 'JAVA', label: 'Java调用' },
  { value: 'WORKFLOW', label: '工作流' }
]

// 表单验证规则
const commandRules = {
  command_type: [
    { required: true, message: '请选择命令类型', trigger: 'blur' }
  ],
  command_value: [
    { required: true, message: '请输入命令内容', trigger: 'blur' }
  ],
  table_data_path: [
    { required: true, message: '请输入表格文件路径', trigger: 'blur' }
  ]
}

// 计算属性
const dialogTitle = computed(() => {
  return isCreating.value ? '新建命令' : '编辑命令'
})

const compiledMarkdown = computed(() => {
  return marked(fileContent.value || '')
})

// 在setup()中添加
const folderFiles = ref({})

// 获取命令列表
const fetchCommandList = async () => {
  try {
    loading.value = true
    const params = {
      page: pagination.current_page,
      page_size: pagination.page_size,
      type: queryParams.command_type,
      search: queryParams.search_key
    }

    if (queryParams.date_range?.length === 2) {
      params.start_date = queryParams.date_range[0]
      params.end_date = queryParams.date_range[1]
    }

    const res = await axios.get('/api/commands', { params })
    
    // 获取每个命令对应的文件夹下的所有文件
    const commandsWithFiles = await Promise.all(
      res.data.data.map(async command => {
        const filesRes = await axios.get(`/api/commands/folder/${encodeURIComponent(command.out_folder_path)}/files`)
        return {
          ...command,
          file_paths: filesRes.data.files.map(file => ({
            full_path: file.full_path,
            file_name: file.file_name,
            created_at: file.created_at
          }))
        }
      })
    )

    commandList.value = commandsWithFiles
    pagination.total = res.data.pagination.total_items
  } catch (error) {
    ElMessage.error('加载命令列表失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

// 新增文件夹预览方法
const previewFolder = (folderPath) => {
  if (!folderPath) return
  const encodedPath = encodeURIComponent(folderPath.replace(/\\/g, '/'))
  window.open(`/api/files/preview?path=${encodedPath}`, '_blank')
}

// 修改文件加载逻辑
const loadFileContent = async (filePath) => {
  try {
    const res = await axios.get('/api/files/content', {
      params: { path: encodeURI(filePath) }
    })
    fileContent.value = res.data.content
    lastSavedTime.value = res.data.timestamp
    unsavedChanges.value = false
  } catch (error) {
    ElMessage.error(`文件加载失败: ${error.message}`)
    throw error
  }
}

// 文件编辑器切换
const toggleFileEditor = async (file, filePath) => {
  if (!filePath) return
  
  // 切换编辑器状态
  if (currentFile.value?.path === filePath) {
    showFileEditor.value = !showFileEditor.value
  } else {
    showFileEditor.value = true
    currentFile.value = { path: filePath }
  }

  // 加载文件内容
  if (showFileEditor.value) {
    try {
      loading.value = true
      await loadFileContent(filePath)
    } catch (e) {
      showFileEditor.value = false
    } finally {
      loading.value = false
    }
  }
}

// 修改预览方法
const previewMarkdown = (filePath) => {
  if (!filePath) {
    ElMessage.warning('文件路径未定义')
    return
  }
  
  // 处理Windows网络路径的特殊情况
  const isNetworkPath = filePath.startsWith('\\\\') || filePath.startsWith('//')
  const encodedPath = isNetworkPath 
    ? encodeURI(filePath)  // 对网络路径使用encodeURI
    : encodeURIComponent(filePath)
  
  window.open(`/preview?path=${encodedPath}`, '_blank')
}

// 修改保存逻辑适配新路径结构
const saveFileContent = async (row, filePath) => {
  try {
    savingFile.value = true
    const res = await axios.put('/api/files/save', {
      path: filePath,
      content: fileContent.value
    })
    
    // 更新关联命令的路径信息
    const updatedCommand = commandList.value.find(cmd => 
      cmd.file_paths.some(f => f.full_path === filePath)
    )
    if (updatedCommand) {
      updatedCommand.updated_at = res.data.timestamp
    }
    
    ElMessage.success({
      message: `文件保存成功: ${getFileName(filePath)}`,
      duration: 3000,
      showClose: true
    })
    
    // 更新文件状态
    fileStatus.value = {
      ...fileStatus.value,
      [filePath]: {
        type: 'success',
        text: '已保存'
      }
    }
    
  } catch (error) {
    ElMessage.error({
      message: `保存失败: ${error.response?.data?.error || error.message}`,
      duration: 5000,
      showClose: true
    })
    
    fileStatus.value = {
      ...fileStatus.value,
      [filePath]: {
        type: 'danger',
        text: '保存失败'
      }
    }
  } finally {
    savingFile.value = false
  }
}

const reloadFileContent = async (filePath) => {
  if (!filePath) {
    ElMessage.warning('文件路径不存在');
    return;
  }

  if (unsavedChanges.value) {
    try {
      await ElMessageBox.confirm('有未保存的更改，确认重新加载吗？', '提示', {
        confirmButtonText: '确认',
        cancelButtonText: '取消',
        type: 'warning'
      });
    } catch {
      return;
    }
  }
  
  try {
    await loadFileContent(filePath);
    ElMessage.success('文件重新加载成功');
  } catch (error) {
    ElMessage.error('重新加载失败: ' + error.message);
  }
}

const handleContentChange = () => {
  unsavedChanges.value = true
}

// 获取文件夹文件列表
const getFolderFiles = (row) => {
  return folderFiles.value[row.out_folder_path] || []
}

// 修改后的文件预览方法
const previewFile = (file) => {
  if (!file) return
  const fullPath = `${file.out_folder_path}/${file.file_name}`
  window.open(`/api/files/content?path=${encodeURIComponent(fullPath)}`)
}

// 修改文件路径获取方式
const getFileName = (path) => {
  return path?.split(/[\\/]/).pop() || ''
}

const handleCreateCommand = () => {
  isCreating.value = true
  Object.assign(editingCommand, {
    id: null,
    command_value: '',
    command_type: 'CLP',
    table_data_path: ''
  })
  
  commandDialogVisible.value = true
}

const handleEditCommand = (command) => {
  isCreating.value = false
  Object.assign(editingCommand, {
    id: command.id,
    command_value: command.command_value,
    command_type: command.command_type,
    table_data_path: command.table_data_path
  })
  
  commandDialogVisible.value = true
}

const handleSaveCommand = async () => {
  try {
    await commandFormRef.value.validate()
    
    if (isCreating.value) {
      await axios.post('/api/commands', editingCommand)
      ElMessage.success('命令创建成功')
    } else {
      await axios.put(`/api/commands/${editingCommand.id}`, editingCommand)
      ElMessage.success('命令更新成功')
    }
    
    commandDialogVisible.value = false
    fetchCommandList()
  } catch (error) {
    if (error.response?.data?.error) {
      ElMessage.error('操作失败: ' + error.response.data.error)
    }
  }
}

const handleDeleteCommand = async (command) => {
  try {
    await ElMessageBox.confirm(
      '确认删除该命令及其关联文件吗？此操作不可恢复！',
      '警告',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger'
      }
    )
    
    await axios.delete(`/api/commands/${command.id}`)
    ElMessage.success('命令删除成功')
    
    if (currentCommand.value?.id === command.id) {
      currentCommand.value = null
      showFileEditor.value = false
    }
    
    fetchCommandList()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败: ' + error.message)
    }
  }
}

const handlePageChange = (page) => {
  pagination.current_page = page
  fetchCommandList()
}

const handleSizeChange = (size) => {
  pagination.page_size = size
  fetchCommandList()
}

const handleSearch = () => {
  pagination.current_page = 1
  fetchCommandList()
}

const getCommandTypeStyle = (type) => {
  const typeMap = {
    CLP: 'success',
    RPGLE: 'warning',
    JAVA: 'info',
    WORKFLOW: 'danger'
  }
  return typeMap[type] || ''
}

const formatDateTime = (isoString) => {
  if (!isoString) return ''
  const date = new Date(isoString)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  })
}

// 增强智能体调用逻辑
const callDifyAgent = async (row, filePath) => {
  try {
    callingAgent.value = true
    currentCallingFile.value = filePath
    
    // 获取标准化后的文件内容
    const fileRes = await axios.get('/api/files/content', {
      params: { path: encodeURIComponent(filePath) }
    })
    
    // 调用后端代理接口
    const res = await axios.post('/api/commands/call-dify-agent', {
      command_id: row.command_value,
      two_dimensional_file: fileRes.data.content,
      file_metadata: {
        path: filePath,
        folder: row.out_folder_path,
        filename: getFileName(filePath)
      }
    })
    
    // 处理响应结果
    ElMessage.success('智能体处理完成')
    console.log('Dify响应:', res.data)
  } catch (error) {
    ElMessage.error('调用智能体失败: ' + error.message)
    console.error('调用智能体失败:', error)
  } finally {
    callingAgent.value = false
    currentCallingFile.value = null
  }
}

// 增强行点击处理
const handleRowClick = (row) => {
  currentCommand.value = row || null
  showFileEditor.value = false
}

// 在script部分添加分组逻辑
const groupedCommands = computed(() => {
  const groups = {}
  commandList.value.forEach(command => {
    if (!groups[command.command_value]) {
      groups[command.command_value] = {
        command_value: command.command_value,
        command_type: command.command_type,
        folders: {}
      }
    }
    
    if (!groups[command.command_value].folders[command.out_folder_path]) {
      groups[command.command_value].folders[command.out_folder_path] = {
        out_folder_path: command.out_folder_path,
        files: []
      }
    }
    
    // 添加文件夹下的所有文件
    command.file_paths.forEach(file => {
      groups[command.command_value].folders[command.out_folder_path].files.push({
        ...file,
        full_path: file.full_path.replace(/\\/g, '/')
      })
    })
  })
  return Object.values(groups)
})

// 初始化加载
fetchCommandList()
</script>

<!-- 保留之前修复的CSS部分 -->
<style scoped>
.command-management-container {
  padding: 20px;
}

.query-section {
  margin-bottom: 20px;
  padding: 15px;
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
}

.command-list-section {
  margin-bottom: 20px;
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
}

.pagination-section {
  display: flex;
  justify-content: flex-end;
  padding: 15px;
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
}

.file-content-section {
  padding: 15px;
  background-color: #fafafa;
  border-radius: 4px;
}

.path-list-header {
  display: flex;
  align-items: center;
  margin-bottom: 15px;
  padding: 10px;
  background-color: #f8f9fa;
}

.path-item {
  margin-bottom: 10px;
}

.path-header {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  background-color: #f5f7fa;
  border-radius: 4px;
  cursor: pointer;
}

.file-time {
  margin-left: auto;
  color: #909399;
  font-size: 12px;
}

.rotate-icon {
  transform: rotate(90deg);
  transition: transform 0.3s;
}

.file-editor-container {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-top: 10px;
  padding: 15px;
  background: #f8f9fa;
  border: 1px solid #ebeef5;
  border-radius: 4px;
}

.editor-area {
  height: 600px;
}

.preview-area {
  height: 600px;
  overflow-y: auto;
  padding: 10px;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid #eee;
}

.markdown-preview {
  overflow-y: auto;
  max-height: 600px;
}

.editor-actions {
  grid-column: span 2;
  display: flex;
  align-items: center;
  gap: 15px;
  padding-top: 10px;
}

.last-saved {
  margin-left: 15px;
  color: #909399;
  font-size: 12px;
}

.path-hint {
  margin-top: 8px;
  padding: 8px;
  background-color: #f5f7fa;
  border-radius: 4px;
  color: #606266;
  font-size: 12px;
  line-height: 1.5;
}
</style>


