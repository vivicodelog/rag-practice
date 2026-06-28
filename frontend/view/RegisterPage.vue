<template>
  <div class="auth-page">
    <div class="auth-card">
      <h2>注册</h2>
      <form @submit.prevent="handleRegister">
        <div class="field">
          <label>用户名</label>
          <input v-model="username" type="text" placeholder="请输入用户名" required />
        </div>
        <div class="field">
          <label>密码</label>
          <input v-model="password" type="password" placeholder="请输入密码" required />
        </div>
        <p v-if="error" class="error">{{ error }}</p>
        <p v-if="success" class="success">注册成功，请登录</p>
        <button type="submit" class="btn-primary" :disabled="loading">
          {{ loading ? '注册中...' : '注册' }}
        </button>
      </form>
      <p class="switch-link">
        已有账号？<a href="#" @click.prevent="$emit('switch', 'login')">登录</a>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const emit = defineEmits(['switch'])

const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')
const success = ref(false)

async function handleRegister() {
  loading.value = true
  error.value = ''
  success.value = false
  try {
    const res = await fetch('http://localhost:8000/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username.value, password: password.value }),
    })
    if (!res.ok) {
      const msg = await res.json()
      throw new Error(msg.detail || '注册失败')
    }
    success.value = true
    username.value = ''
    password.value = ''
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: calc(100vh - 120px);
}
.auth-card {
  background: #fff;
  padding: 40px;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
  width: 380px;
}
.auth-card h2 {
  text-align: center;
  margin-bottom: 24px;
  font-size: 22px;
  color: #333;
}
.field {
  margin-bottom: 16px;
}
.field label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: #555;
  margin-bottom: 6px;
}
.field input {
  width: 100%;
  padding: 10px 12px;
  font-size: 14px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  outline: none;
  transition: border-color 0.15s;
}
.field input:focus {
  border-color: #4a90d9;
}
.btn-primary {
  width: 100%;
  padding: 10px;
  font-size: 15px;
  font-weight: 500;
  color: #fff;
  background: #4a90d9;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  margin-top: 8px;
}
.btn-primary:disabled {
  background: #a0c4e8;
  cursor: not-allowed;
}
.error {
  color: #e74c3c;
  font-size: 13px;
  margin-bottom: 4px;
}
.success {
  color: #27ae60;
  font-size: 13px;
  margin-bottom: 4px;
}
.switch-link {
  text-align: center;
  margin-top: 18px;
  font-size: 13px;
  color: #888;
}
.switch-link a {
  color: #4a90d9;
  text-decoration: none;
}
</style>
