import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import {
  chatApi,
  chatResourceApi,
  type ChatConfiguration,
  type ChatConversation,
  type ChatMessage,
  type ChatSession,
} from '../api/chat'
import { saveRetrievalKbPreference } from '../lib/retrieval-kb-preference'
import { useAuthStore } from './auth'

export const useChatStore = defineStore('chat', () => {
  const conversations = ref<ChatConversation[]>([])
  const activeConversationId = ref<string | null>(null)
  const sessionsInConversation = ref<ChatSession[]>([])

  const activeSessionId = ref<string | null>(null)
  const activeSession = ref<ChatSession | null>(null)
  const activeConfiguration = ref<ChatConfiguration | null>(null)
  const messages = ref<ChatMessage[]>([])
  const isGenerating = ref(false)

  const activeConversation = computed(() =>
    conversations.value.find((c) => c.id === activeConversationId.value) ?? null,
  )

  const fetchConversations = async () => {
    try {
      const res = await chatResourceApi.list()
      conversations.value = res.data
    } catch (e) {
      console.error('Failed to fetch conversations', e)
    }
  }

  const refreshSessionsInConversation = async () => {
    if (!activeConversationId.value) {
      sessionsInConversation.value = []
      return
    }
    try {
      const res = await chatResourceApi.listSessions(activeConversationId.value)
      sessionsInConversation.value = res.data
    } catch (e) {
      console.error('Failed to fetch sessions for conversation', e)
    }
  }

  const selectSession = async (sessionId: string) => {
    activeSessionId.value = sessionId
    try {
      const [sessionRes, configRes, msgRes] = await Promise.all([
        chatApi.getSession(sessionId),
        chatApi.getConfiguration(sessionId),
        chatApi.getMessages(sessionId),
      ])
      activeSession.value = sessionRes.data
      activeConfiguration.value = configRes.data
      messages.value = msgRes.data
    } catch (e) {
      console.error('Failed to select session', e)
    }
  }

  const selectConversation = async (conversationId: string) => {
    activeConversationId.value = conversationId
    await refreshSessionsInConversation()
    const list = sessionsInConversation.value
    if (list.length > 0) {
      await selectSession(list[0].id)
    } else {
      activeSessionId.value = null
      activeSession.value = null
      activeConfiguration.value = null
      messages.value = []
    }
  }

  const leaveConversation = () => {
    activeConversationId.value = null
    sessionsInConversation.value = []
    activeSessionId.value = null
    activeSession.value = null
    activeConfiguration.value = null
    messages.value = []
  }

  const createConversation = async (title: string, configuration?: Partial<ChatConfiguration>) => {
    const res = await chatResourceApi.create(title, configuration)
    await selectConversation(res.data.id)
    conversations.value.unshift(res.data)
    return res.data
  }

  const createSessionInActiveConversation = async (title: string) => {
    if (!activeConversationId.value) return
    try {
      const res = await chatResourceApi.createSession(activeConversationId.value, title)
      await refreshSessionsInConversation()
      await selectSession(res.data.id)
      await fetchConversations()
      return res.data
    } catch (e) {
      console.error('Failed to create session', e)
    }
  }

  const updateConversationTitle = async (conversationId: string, title: string) => {
    try {
      const res = await chatResourceApi.update(conversationId, title)
      const index = conversations.value.findIndex((c: ChatConversation) => c.id === conversationId)
      if (index !== -1) {
        conversations.value[index] = res.data
      }
    } catch (e) {
      console.error('Failed to update conversation title', e)
    }
  }

  const deleteConversation = async (conversationId: string) => {
    try {
      await chatResourceApi.delete(conversationId)
      conversations.value = conversations.value.filter((c) => c.id !== conversationId)
      if (activeConversationId.value === conversationId) {
        leaveConversation()
      }
    } catch (e) {
      console.error('Failed to delete conversation', e)
    }
  }

  const updateSessionTitle = async (sessionId: string, title: string) => {
    try {
      const res = await chatApi.updateSession(sessionId, title)
      const index = sessionsInConversation.value.findIndex((s: ChatSession) => s.id === sessionId)
      if (index !== -1) {
        sessionsInConversation.value[index] = res.data
      }
      if (activeSessionId.value === sessionId) {
        activeSession.value = res.data
      }
      await fetchConversations()
    } catch (e) {
      console.error('Failed to update session title', e)
    }
  }

  const deleteSession = async (sessionId: string) => {
    const convId = activeConversationId.value
    try {
      await chatApi.deleteSession(sessionId)
      sessionsInConversation.value = sessionsInConversation.value.filter((s) => s.id !== sessionId)

      if (sessionsInConversation.value.length === 0) {
        if (convId != null) {
          conversations.value = conversations.value.filter((c) => c.id !== convId)
        }
        leaveConversation()
        await fetchConversations()
        return
      }

      if (activeSessionId.value === sessionId) {
        await selectSession(sessionsInConversation.value[0].id)
      }
      await fetchConversations()
    } catch (e) {
      console.error('Failed to delete session', e)
    }
  }

  const deleteSessionsBatch = async (sessionIds: string[]) => {
    const uniq = [...new Set(sessionIds)]
    if (uniq.length === 0) {
      return
    }
    const convId = activeConversationId.value
    if (!convId) {
      return
    }
    const idSet = new Set(uniq)
    try {
      await Promise.all(uniq.map((id) => chatApi.deleteSession(id)))
    } catch (e) {
      console.error('Failed to delete sessions (batch)', e)
      await refreshSessionsInConversation()
      throw e
    }

    sessionsInConversation.value = sessionsInConversation.value.filter((s) => !idSet.has(s.id))

    if (sessionsInConversation.value.length === 0) {
      conversations.value = conversations.value.filter((c) => c.id !== convId)
      leaveConversation()
      await fetchConversations()
      return
    }

    if (activeSessionId.value != null && idSet.has(activeSessionId.value)) {
      await selectSession(sessionsInConversation.value[0].id)
    }
    await fetchConversations()
  }

  const updateConfiguration = async (configuration: Partial<ChatConfiguration>) => {
    if (!activeSessionId.value) return
    try {
      const res = await chatApi.updateConfiguration(activeSessionId.value, configuration)
      activeConfiguration.value = res.data
      if (configuration.knowledge_base_ids !== undefined) {
        const auth = useAuthStore()
        const sid = auth.currentSpace?.id ?? 0
        saveRetrievalKbPreference(sid, auth.currentSpaceSlug, configuration.knowledge_base_ids)
      }
    } catch (e) {
      console.error('Failed to update configuration', e)
    }
  }

  const appendMessageContent = (messageId: string, delta: string) => {
    const i = messages.value.findIndex((m: ChatMessage) => m.id === messageId)
    if (i === -1) {
      return
    }
    const cur = messages.value[i]
    messages.value[i] = { ...cur, content: cur.content + delta }
  }

  const replaceMessage = (oldId: string, message: ChatMessage) => {
    const i = messages.value.findIndex((m: ChatMessage) => m.id === oldId)
    if (i === -1) {
      messages.value.push(message)
      return
    }
    messages.value[i] = message
  }

  const setGenerating = (value: boolean) => {
    isGenerating.value = value
  }

  const addMessage = (message: ChatMessage) => {
    messages.value.push(message)
  }

  const removeMessageById = (messageId: string) => {
    const i = messages.value.findIndex((m: ChatMessage) => m.id === messageId)
    if (i !== -1) {
      messages.value.splice(i, 1)
    }
  }

  return {
    conversations,
    activeConversationId,
    sessionsInConversation,
    activeSessionId,
    activeSession,
    activeConversation,
    activeConfiguration,
    messages,
    isGenerating,
    fetchConversations,
    refreshSessionsInConversation,
    selectConversation,
    selectSession,
    leaveConversation,
    createConversation,
    createSessionInActiveConversation,
    updateConversationTitle,
    deleteConversation,
    updateSessionTitle,
    deleteSession,
    deleteSessionsBatch,
    updateConfiguration,
    addMessage,
    appendMessageContent,
    replaceMessage,
    setGenerating,
    removeMessageById,
  }
})
