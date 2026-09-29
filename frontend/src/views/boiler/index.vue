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
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              :disabled="!isActionAllowed(action, row)"
              :title="isActionAllowed(action, row) ? action : `当前「${row['设备状态']}」状态不能${action}`"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无锅炉设备数据，可先登记锅炉设备</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条锅炉设备记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/boiler'
const columns = ["设备编号", "设备名称", "额定蒸发量", "工作压力", "使用场所", "投用日期", "下次检验日", "设备状态"]
const actions = ["办理投用", "安排检修", "报废设备"] as const
// 与后端状态机保持一致：只有当前状态允许的动作才可点击，非法流转直接置灰。
const ACTIONS_BY_STATUS: Record<string, readonly string[]> = {
  "待投用": ["办理投用"],
  "在用运行": ["安排检修", "报废设备"],
  "停炉检修": ["办理投用", "报废设备"],
  "已报废": [],
}
const stats = [{"label": "在用锅炉", "value": 0}, {"label": "停炉检修", "value": 0}, {"label": "临近检验", "value": 0}]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

function activeQuery() {
  return new URLSearchParams(filters.value as Record<string, string>).toString()
}

function isActionAllowed(action: string, row: Row) {
  const allowed = ACTIONS_BY_STATUS[String(row['设备状态'] ?? '')] ?? []
  return allowed.includes(action)
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  // 导出地址与列表共用同一套过滤参数，保证导出内容与列表对得上。
  const query = activeQuery()
  window.open(`${ENDPOINT}/export${query ? `?${query}` : ''}`, '_blank')
}

function openCreate() {
  errorMessage.value = '锅炉设备登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  if (!isActionAllowed(action, row)) {
    errorMessage.value = `锅炉设备当前为「${row['设备状态']}」，不能${action}`
    return
  }
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('锅炉设备动作未生效，请稍后重试')
    }
    const payload = await response.json()
    // HTTP 200 也可能是业务拦截（ok=false），需要把后端说明展示出来并保持列表不被改乱。
    if (!payload.ok) {
      throw new Error(payload.message || '锅炉设备动作未生效')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '锅炉设备操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = activeQuery()
  try {
    const response = await request(`${ENDPOINT}${query ? `?${query}` : ''}`)
    if (!response.ok) {
      throw new Error('锅炉设备列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '锅炉设备列表读取失败'
  }
}

onMounted(reload)
</script>
