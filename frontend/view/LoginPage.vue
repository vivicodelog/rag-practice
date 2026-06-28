<template>
  <div class="auth-page">
    <div class="auth-card">
      <h2>登录</h2>
      <form @submit.prevent="handleLogin">
        <div class="field">
          <label>用户名</label>
          <input v-model="username" type="text" placeholder="请输入用户名" required />
        </div>
        <div class="field">
          <label>密码</label>
          <input v-model="password" type="password" placeholder="请输入密码" required />
        </div>
        <p v-if="error" class="error">{{ error }}</p>
        <button type="submit" class="btn-primary" :disabled="loading">
          {{ loading ? '登录中...' : '登录' }}
        </button>
      </form>
      <p class="switch-link">
        还没有账号？<a href="#" @click.prevent="$emit('switch', 'register')">注册</a>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const emit = defineEmits(['login-success', 'switch'])

const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function handleLogin() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetch('http://localhost:8000/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username.value, password: password.value }),
    })
    if (!res.ok) {
      const msg = await res.json()
      throw new Error(msg.detail || '登录失败')
    }
    const data = await res.json()
    // token / user_id 由你在 api.js 统一管理
    emit('login-success', data)
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
