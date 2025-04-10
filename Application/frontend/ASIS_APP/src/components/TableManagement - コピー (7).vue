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
            <div class="folder-structure">
              <el-table 
                :data="row.folders"
                row-key="out_folder_path"
                :tree-props="{ children: 'children' }"
              >
                <el-table-column label="存储路径" width="350">
                  <template #default="{ row: folder }">
                    <div style="display: flex; align-items: center">
                      <el-icon v-if="folder.children.length > 0">
                        <FolderOpened />
                      </el-icon>
                      <el-icon v-else>
                        <Folder />
                      </el-icon>
                      <el-link 
                        class="folder-link"
                        @click="previewFolder(folder.out_folder_path)"
                      >
                        {{ folder.out_folder_path }}
                      </el-link>
                    </div>
                  </template>
                </el-table-column>

                <el-table-column label="文件列表">
                  <template #default="{ row: folder }">
                    <div v-for="file in folder.files" :key="file.full_path">
                      <div class="file-item-container">
                        <div class="file-header">
                          <el-link 
                            @click="() => toggleFileEditor(file, file.full_path)"
                            :class="{ 'active-file': currentFile?.path === file.full_path }"
                          >
                            <el-icon :class="{'rotate-icon': showFileEditor && currentFile?.path === file.full_path}">
                              <ArrowRight />
                            </el-icon>
                            {{ file.file_name }}
                          </el-link>
                          
                          <div class="file-actions">
                            <!-- <el-button 
                              type="info" 
                              size="small" 
                              @click.stop="previewMarkdown(file.full_path)"
                            >
                              <el-icon><View /></el-icon>
                              预览
                            </el-button> -->
                            <el-button 
                              v-if="file.file_name.toLowerCase().includes('two-dimensional')"
                              type="primary" 
                              size="small" 
                              @click.stop="() => callDifyAgent(file)"
                              :loading="callingAgent && currentCallingFile?.path === file.full_path"
                            >
                              <el-icon><MagicStick /></el-icon>
                              调用智能体
                            </el-button>
                          </div>
                          
                          <span class="file-time">
                            {{ formatDateTime(file.created_at) }}
                          </span>
                        </div>

                        <!-- 保留编辑器容器 -->
                        <div 
                          v-if="showFileEditor && currentFile?.path === file.full_path"
                          class="file-editor-container"
                        >
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
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </template>
        </el-table-column>

        <!-- 操作列 -->
        <el-table-column label="操作" width="150" align="center">
          <template #default="{ row }">
            <el-button 
              type="primary" 
              size="small" 
              @click="callDifyAgentForTable(row)"
              :loading="callingAgentForTable && currentCallingFileForTable?.path === row.command_value"
            >
              <el-icon><MagicStick /></el-icon>
              <span>调用二维表智能体</span>
            </el-button>
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

    <!-- 修改命令编辑对话框 -->
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
  Upload, InfoFilled, ArrowRight, Refresh, MagicStick, Files, Folder, FolderOpened 
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
const callingAgentForTable = ref(false)
const currentCallingFileForTable = ref(null)

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
  out_folder_path: ''
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
    
    const commandsWithFiles = await Promise.all(
      res.data.data.map(async command => {
        const filesRes = await axios.get(`/api/commands/folder/${encodeURIComponent(command.out_folder_path)}/files`)
        return {
          ...command,
          file_paths: filesRes.data.files.map(file => ({
            ...file,
            command_value: command.command_value  // 添加命令内容到文件对象
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
    out_folder_path: ''
  })
  
  commandDialogVisible.value = true
}

const handleEditCommand = (command) => {
  isCreating.value = false
  Object.assign(editingCommand, {
    id: command.id,
    command_value: command.command_value,
    command_type: command.command_type,
    out_folder_path: command.out_folder_path
  })
  
  commandDialogVisible.value = true
}

const handleSaveCommand = async () => {
  try {
    await commandFormRef.value.validate()
    
    // 生成 OutFolderPath，去除开头的 @
    const outFolderPath = `\\\\192.168.9.177\\shared\\ASIS_OUT_DIFY\\${editingCommand.command_value}`
    
    // 添加 OutFolderPath 到请求数据，并确保字段名与后端模型一致
    const commandData = {
      CommandValue: editingCommand.command_value,  // 修改为 CommandValue
      CommandType: editingCommand.command_type,    // 修改为 CommandType
      OutFolderPath: outFolderPath                 // 修改为 OutFolderPath
    }
    
    if (isCreating.value) {
      await axios.post('/api/commands', commandData)
      ElMessage.success('命令创建成功')
    } else {
      await axios.put(`/api/commands/${editingCommand.id}`, commandData)
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

// 外层命令调用二维表智能体
const callDifyAgentForTable = async (row) => {
  try {
    callingAgentForTable.value = true
    currentCallingFileForTable.value = { path: row.command_value }  // 使用命令值作为标识
    
    const res = await axios.post('/api/commands/call-dify-agent-for-table', {
      command_id: row.command_value  // 直接使用命令内容
    })
    
    ElMessage.success('二维表生成请求已提交')
    console.log('Dify响应:', res.data)
  } catch (error) {
    ElMessage.error('调用失败: ' + error.message)
  } finally {
    callingAgentForTable.value = false
    currentCallingFileForTable.value = null
  }
}

// 文件级智能体调用保持不变
const callDifyAgent = async (file) => {
  try {
    callingAgent.value = true
    currentCallingFile.value = { path: file.full_path }
    
    const fileRes = await axios.get('/api/files/content', {
      params: { path: encodeURIComponent(file.full_path) }
    })
    
    const res = await axios.post('/api/commands/call-dify-agent', {
      command_id: file.command_value,  // 使用文件所属命令的command_value
      two_dimensional_file: fileRes.data.content
    })
    
    ElMessage.success('智能体处理完成')
  } catch (error) {
    ElMessage.error('调用失败: ' + error.message)
  } finally {
    callingAgent.value = false
    currentCallingFile.value = null
  }
}

// 修改分组逻辑
const groupedCommands = computed(() => {
  const groups = {}
  
  commandList.value.forEach(command => {
    const key = command.command_value
    if (!groups[key]) {
      groups[key] = {
        command_value: key,
        command_type: command.command_type,
        folders: []
      }
    }
    
    // 直接使用完整路径作为节点
    const existing = groups[key].folders.find(f => f.out_folder_path === command.out_folder_path)
    if (!existing) {
      groups[key].folders.push({
        out_folder_path: command.out_folder_path,
        files: command.file_paths.map(f => ({
          ...f,
          full_path: f.full_path.replace(/\\/g, '/')
        })),
        children: []
      })
    }
  })

  // 构建层级关系
  Object.values(groups).forEach(group => {
    group.folders.sort((a, b) => a.out_folder_path.localeCompare(b.out_folder_path))
    
    group.folders.forEach(folder => {
      const parentPath = folder.out_folder_path.replace(/[\\/][^\\/]+$/, '')
      const parent = group.folders.find(f => f.out_folder_path === parentPath)
      if (parent) {
        parent.children.push(folder)
      }
    })
    
    group.folders = group.folders.filter(f => !group.folders.some(
      p => p.out_folder_path !== f.out_folder_path && 
      f.out_folder_path.startsWith(p.out_folder_path)
    ))
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
  margin-top: 10px;
  padding: 15px;
  background: #fff;
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

.folder-structure {
  padding: 15px;
  background-color: #fafafa;
  border-radius: 4px;
}

.folder-node {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
}

.folder-name {
  margin-left: 10px;
  font-weight: bold;
}

.child-folder {
  margin-left: 20px;
}

.folder-link {
  margin-left: 10px;
}

.file-item-container {
  margin-bottom: 15px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 10px;
}

.file-header {
  display: flex;
  align-items: center;
  cursor: pointer;
  padding: 8px;
  background-color: #f8f9fa;
  border-radius: 4px;
}

.file-actions {
  margin-left: auto;
  display: flex;
  gap: 10px;
}

.active-file {
  color: #409eff;
  font-weight: bold;
}
</style>


