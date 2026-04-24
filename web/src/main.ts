import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { useAppStore } from './stores/app'
import './styles.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
useAppStore(pinia).initTheme()
app.use(router)
app.mount('#app')
