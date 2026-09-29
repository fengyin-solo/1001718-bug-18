<template>
  <section class="page" data-module="boiler">
    <header class="page-head">
      <div>
        <h2>锅炉设备管理</h2>
        <p class="page-desc">维护锅炉设备，围绕设备编号、设备名称、额定蒸发量、工作压力做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记锅炉设备</button>
        <button class="btn" type="button" @click="exportRows">导出锅炉设备清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>设备编号</span>
        <input v-model="filters.keyword" placeholder="按设备编号检索" />
      </label>
      <label class="filter-item">
        <span>设备状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
          <th>流转记录</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <template v-if="(row.actions ?? []).length">
              <button
                v-for="action in row.actions"
                :key="action"
                class="link"
                type="button"
                @click="runAction(action, row)"
              >
                {{ action }}
              </button>
            </template>
            <span v-else class="muted">已报废</span>
          </td>
          <td>
            <button class="link" type="button" @click="toggleRecords(row)">
              {{ expandedId === row.id ? '收起记录' : `查看记录（${(row.records ?? []).length}）` }}
            </button>
          </td>
        </tr>
        <tr v-if="expandedRow" class="records-row">
          <td :colspan="columns.length + 2">
            <div class="records-box">
              <h4>{{ expandedRow['设备编号'] }} · 流转记录</h4>
              <ol class="records-list">
                <li v-for="(record, index) in (expandedRow.records ?? [])" :key="index">
                  <span class="rec-time">{{ record.time || '—' }}</span>
                  <span class="rec-action">{{ record.action }}</span>
                  <span class="rec-flow">{{ record.from_status || '入库' }} → {{ record.to_status }}</span>
                  <span class="rec-note">{{ record.note || '' }}</span>
                </li>
                <li v-if="!(expandedRow.records ?? []).length" class="empty-state">暂无流转记录</li>
              </ol>
            </div>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 2" class="empty-state">暂无锅炉设备数据，可先登记锅炉设备</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条锅炉设备记录</span>
      <span v-if="infoMessage" class="info-text">{{ infoMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="showCreate" class="modal-mask" @click.self="showCreate = false">
      <div class="modal">
        <h3>登记锅炉设备</h3>
        <label v-for="field in createFields" :key="field" class="modal-field">
          <span>{{ field }}<em v-if="requiredFields.includes(field)"> *</em></span>
          <input v-model="createForm[field]" :placeholder="`请输入${field}`" />
        </label>
        <div class="modal-actions">
          <button class="btn primary" type="button" @click="submitCreate">提交登记</button>
          <button class="btn ghost" type="button" @click="showCreate = false">取消</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, any>
type FlowRecord = {
  action: string
  from_status: string | null
  to_status: string
  time: string
  note?: string
}

const ENDPOINT = '/api/boiler'
const columns = ["设备编号", "设备名称", "额定蒸发量", "工作压力", "使用场所", "投用日期", "下次检验日", "设备状态"]
const statuses = ["待投用", "在用运行", "停炉检修", "已报废"]
const createFields = ["设备编号", "设备名称", "额定蒸发量", "工作压力", "使用场所", "投用日期", "下次检验日"]
const requiredFields = ["设备编号", "设备名称", "额定蒸发量"]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const infoMessage = ref('')
const filters = ref<{ keyword: string; status: string }>({ keyword: '', status: '' })
const expandedId = ref<number | null>(null)
const showCreate = ref(false)
const createForm = ref<Record<string, string>>({})

const expandedRow = computed(() => rows.value.find((row) => row.id === expandedId.value) ?? null)

const stats = computed(() => [
  { label: '在用锅炉', value: rows.value.filter((row) => row.status === '在用运行').length },
  { label: '停炉检修', value: rows.value.filter((row) => row.status === '停炉检修').length },
  { label: '临近检验', value: rows.value.filter((row) => isDueSoon(row['下次检验日'])).length },
])

function isDueSoon(value: unknown): boolean {
  if (typeof value !== 'string' || !value) return false
  const due = Date.parse(value)
  if (Number.isNaN(due)) return false
  const days = (due - Date.now()) / 86400000
  return days >= 0 && days <= 30
}

function buildQuery(): URLSearchParams {
  const params = new URLSearchParams()
  if (filters.value.keyword.trim()) params.set('keyword', filters.value.keyword.trim())
  if (filters.value.status) params.set('status', filters.value.status)
  return params
}

function resetFilters() {
  filters.value = { keyword: '', status: '' }
  void reload()
}

function exportRows() {
  const query = buildQuery().toString()
  window.open(`${ENDPOINT}/export${query ? `?${query}` : ''}`, '_blank')
}

function openCreate() {
  createForm.value = {}
  showCreate.value = true
}

async function submitCreate() {
  errorMessage.value = ''
  infoMessage.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: createForm.value }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message || '锅炉设备登记未生效，请检查必填字段')
    }
    showCreate.value = false
    infoMessage.value = payload.message || '锅炉设备已登记'
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '锅炉设备登记失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  infoMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message || '锅炉设备动作未生效，请稍后重试')
    }
    infoMessage.value = payload.message || '动作已生效'
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '锅炉设备操作失败'
  }
}

function toggleRecords(row: Row) {
  expandedId.value = expandedId.value === row.id ? null : row.id
}

async function reload() {
  errorMessage.value = ''
  const query = buildQuery().toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    const payload = await response.json().catch(() => null)
    if (!response.ok) {
      throw new Error(payload?.detail ? `锅炉设备列表读取失败：${payload.detail}` : '锅炉设备列表读取失败')
    }
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '锅炉设备列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.muted { color: var(--muted); font-size: 12px; }
.info-text { color: #1f6feb; }
.records-row td { background: #f8fafc; }
.records-box { padding: 4px 8px; }
.records-box h4 { margin: 0 0 8px; font-size: 13px; }
.records-list { margin: 0; padding-left: 20px; font-size: 13px; }
.records-list li { display: flex; gap: 12px; padding: 3px 0; }
.rec-time { color: var(--muted); min-width: 90px; }
.rec-action { font-weight: 600; min-width: 70px; }
.rec-flow { color: #334155; min-width: 130px; }
.rec-note { color: var(--muted); }
.modal-mask {
  position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45);
  display: flex; align-items: center; justify-content: center; z-index: 50;
}
.modal {
  background: #fff; border-radius: 10px; padding: 20px 24px; width: 420px;
  max-width: calc(100vw - 48px);
}
.modal h3 { margin: 0 0 12px; }
.modal-field { display: block; margin-bottom: 10px; font-size: 13px; }
.modal-field span { display: block; color: var(--muted); margin-bottom: 4px; }
.modal-field em { color: #b42318; font-style: normal; }
.modal-field input {
  width: 100%; border: 1px solid var(--border); border-radius: 6px;
  padding: 6px 8px; font-size: 13px;
}
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 14px; }
</style>
