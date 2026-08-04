<script setup lang="ts">
/**
 * 管理端模型计价管理页（M5，8.3）
 *
 * 模型计价配置 CRUD + 启用/停用。
 * 数据来源：GET/POST/PUT /admin/model-pricing。
 */
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { PlusOutlined, ReloadOutlined, EditOutlined } from '@ant-design/icons-vue'

import {
  listModelPricing,
  createModelPricing,
  updateModelPricing,
} from '@/api/pointsController'

interface PricingRow {
  id: number
  category: string
  provider: string
  model: string
  agentName?: string | null
  inputPricePer1k: number
  outputPricePer1k: number
  pricePerImage: number
  enabled: boolean
}

const rows = ref<PricingRow[]>([])
const loading = ref(false)
const modalOpen = ref(false)
const saving = ref(false)
const editingId = ref<number | null>(null)

const form = ref<PricingRow>({
  id: 0,
  category: 'LLM',
  provider: 'Xiaomi',
  model: '',
  agentName: '',
  inputPricePer1k: 0,
  outputPricePer1k: 0,
  pricePerImage: 0,
  enabled: true,
})

const fetchList = async () => {
  loading.value = true
  try {
    const res = await listModelPricing()
    if (res.data.code === 0) {
      rows.value = (res.data.data as PricingRow[]) ?? []
    } else {
      message.error(res.data.message || '获取计价配置失败')
    }
  } catch (e: any) {
    message.error(e?.message || '获取计价配置失败')
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  editingId.value = null
  form.value = {
    id: 0,
    category: 'LLM',
    provider: 'Xiaomi',
    model: '',
    agentName: '',
    inputPricePer1k: 0,
    outputPricePer1k: 0,
    pricePerImage: 0,
    enabled: true,
  }
  modalOpen.value = true
}

const openEdit = (record: PricingRow) => {
  editingId.value = record.id
  form.value = { ...record }
  modalOpen.value = true
}

const toggleEnabled = async (record: PricingRow) => {
  try {
    const res = await updateModelPricing({
      id: record.id,
      category: record.category,
      provider: record.provider,
      model: record.model,
      agentName: record.agentName || '',
      inputPricePer1k: record.inputPricePer1k,
      outputPricePer1k: record.outputPricePer1k,
      pricePerImage: record.pricePerImage,
      enabled: !record.enabled,
    } as any)
    if (res.data.code === 0) {
      message.success(record.enabled ? '已停用' : '已启用')
      fetchList()
    } else {
      message.error(res.data.message || '操作失败')
      fetchList()
    }
  } catch (e: any) {
    message.error(e?.message || '操作失败')
    fetchList()
  }
}

const doSave = async () => {
  if (!form.value.model.trim()) {
    message.warning('请填写模型名')
    return
  }
  saving.value = true
  try {
    const body = {
      category: form.value.category,
      provider: form.value.provider,
      model: form.value.model.trim(),
      agentName: form.value.agentName || '',
      inputPricePer1k: form.value.inputPricePer1k ?? 0,
      outputPricePer1k: form.value.outputPricePer1k ?? 0,
      pricePerImage: form.value.pricePerImage ?? 0,
      enabled: form.value.enabled,
    }
    let res
    if (editingId.value) {
      res = await updateModelPricing({ id: editingId.value, ...body } as any)
    } else {
      res = await createModelPricing(body as any)
    }
    if (res.data.code === 0) {
      message.success(editingId.value ? '更新成功' : '新增成功')
      modalOpen.value = false
      fetchList()
    } else {
      message.error(res.data.message || '保存失败')
    }
  } catch (e: any) {
    message.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

const columns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
  { title: '类别', dataIndex: 'category', key: 'category', width: 90 },
  { title: '提供商', dataIndex: 'provider', key: 'provider', width: 120 },
  { title: '模型', dataIndex: 'model', key: 'model' },
  { title: 'Agent', dataIndex: 'agentName', key: 'agentName', width: 150 },
  { title: '输入单价(积分/1k)', dataIndex: 'inputPricePer1k', key: 'inputPricePer1k', width: 150 },
  { title: '输出单价(积分/1k)', dataIndex: 'outputPricePer1k', key: 'outputPricePer1k', width: 150 },
  { title: '每张图(积分)', dataIndex: 'pricePerImage', key: 'pricePerImage', width: 130 },
  { title: '启用', key: 'enabled', width: 90 },
  { title: '操作', key: 'action', width: 90 },
]

onMounted(fetchList)
</script>

<template>
  <div id="modelPricingPage">
    <div class="page-head">
      <div class="page-head-inner">
        <h1 class="page-title">模型计价管理</h1>
        <p class="page-subtitle">配置各模型积分单价（每 1k token / 每张图），结算时按此计价</p>
        <a-button type="primary" class="add-btn" @click="openCreate">
          <PlusOutlined /> 新增配置
        </a-button>
        <a-button class="refresh-btn" @click="fetchList">
          <ReloadOutlined /> 刷新
        </a-button>
      </div>
    </div>

    <div class="page-body">
      <a-table
        :columns="columns"
        :data-source="rows"
        :loading="loading"
        row-key="id"
        size="middle"
        :pagination="{ pageSize: 20, showTotal: (t: number) => `共 ${t} 条` }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'enabled'">
            <a-switch :checked="record.enabled" @change="toggleEnabled(record)" />
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button type="link" size="small" @click="openEdit(record)">
              <EditOutlined /> 编辑
            </a-button>
          </template>
        </template>
      </a-table>
    </div>

    <a-modal
      v-model:open="modalOpen"
      :title="editingId ? '编辑计价配置' : '新增计价配置'"
      :confirm-loading="saving"
      @ok="doSave"
    >
      <a-form layout="vertical">
        <a-form-item label="类别" required>
          <a-radio-group v-model:value="form.category">
            <a-radio-button value="LLM">LLM</a-radio-button>
            <a-radio-button value="IMAGE">IMAGE</a-radio-button>
          </a-radio-group>
        </a-form-item>
        <a-form-item label="提供商" required>
          <a-input v-model:value="form.provider" placeholder="如 Xiaomi / DeepSeek / Zhipu / NanoBanana" />
        </a-form-item>
        <a-form-item label="模型名" required>
          <a-input v-model:value="form.model" placeholder="如 mimo-v2.5-pro（LLM 通配用 *）" />
        </a-form-item>
        <a-form-item label="Agent 细分（可空=不限）">
          <a-input v-model:value="form.agentName" placeholder="如 title / outline / ai_modify_outline" />
        </a-form-item>
        <template v-if="form.category === 'LLM'">
          <a-form-item label="输入 token 单价（积分/1k token）">
            <a-input-number v-model:value="form.inputPricePer1k" :step="0.1" :precision="4" style="width: 100%" />
          </a-form-item>
          <a-form-item label="输出 token 单价（积分/1k token）">
            <a-input-number v-model:value="form.outputPricePer1k" :step="0.1" :precision="4" style="width: 100%" />
          </a-form-item>
        </template>
        <template v-else>
          <a-form-item label="每张图积分">
            <a-input-number v-model:value="form.pricePerImage" :step="0.5" :precision="2" style="width: 100%" />
          </a-form-item>
        </template>
        <a-form-item label="启用">
          <a-switch v-model:checked="form.enabled" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<style scoped>
#modelPricingPage {
  min-height: 100vh;
  background: var(--color-background-secondary, #f8fafc);
  padding-bottom: 48px;
}

.page-head {
  background: #fff;
  border-bottom: 1px solid var(--color-border, #e2e8f0);
  padding: 28px 0;
}
.page-head-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.page-title {
  font-size: 26px;
  font-weight: 700;
  margin: 0 0 6px;
  color: var(--color-text, #1f2937);
  flex-basis: 100%;
}
.page-subtitle {
  font-size: 14px;
  color: var(--color-text-secondary, #475569);
  margin: 0;
  flex: 1;
}
.add-btn {
  margin-left: auto;
}

.page-body {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}
</style>