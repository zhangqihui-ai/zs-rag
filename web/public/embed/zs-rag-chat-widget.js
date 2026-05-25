/**
 * ZS-RAG 对话浮动嵌入：在宿主页右下角展示气泡按钮，点击展开 iframe。
 *
 * 使用前在页面中设置 window.zsRagChatEmbedConfig，再加载本脚本（defer）。
 * 配置项见文末注释。
 */
;(function () {
  if (typeof document === 'undefined') return

  var cfg = window.zsRagChatEmbedConfig || {}
  var scriptEl = document.currentScript
  var originFromScript = ''
  if (scriptEl && scriptEl.src) {
    try {
      originFromScript = new URL(scriptEl.src, document.baseURI).origin
    } catch (e) {
      /* noop */
    }
  }

  var iframeSrc = cfg.src
  if (!iframeSrc && originFromScript) {
    iframeSrc = originFromScript.replace(/\/$/, '') + '/chat/embed'
  }
  if (!iframeSrc) {
    console.warn('[zs-rag-chat-embed] 请在 zsRagChatEmbedConfig 中设置 src（嵌入入口完整 URL，一般为 …/chat/embed）')
    return
  }

  var bubbleColor = cfg.bubbleColor || '#1C64F2'
  var panelW = cfg.panelWidth || '24rem'
  var panelH = cfg.panelHeight || '40rem'
  var title = cfg.title || '知识对话'

  if (document.getElementById('zs-rag-chat-embed-root')) return

  var root = document.createElement('div')
  root.id = 'zs-rag-chat-embed-root'
  document.body.appendChild(root)

  var btn = document.createElement('button')
  btn.id = 'zs-rag-chat-embed-button'
  btn.type = 'button'
  btn.setAttribute('aria-label', cfg.bubbleLabel || '打开对话')
  btn.setAttribute('aria-expanded', 'false')
  btn.innerHTML =
    '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>'
  btn.style.cssText =
    'position:fixed;bottom:1.25rem;right:1.25rem;width:3.5rem;height:3.5rem;border-radius:9999px;border:none;cursor:pointer;' +
    'box-shadow:0 4px 14px rgba(0,0,0,.2);z-index:2147483000;display:flex;align-items:center;justify-content:center;' +
    'background:' +
    bubbleColor +
    ';transition:transform .15s ease'
  btn.addEventListener('mouseenter', function () {
    btn.style.transform = 'scale(1.05)'
  })
  btn.addEventListener('mouseleave', function () {
    btn.style.transform = 'scale(1)'
  })

  var panel = document.createElement('div')
  panel.id = 'zs-rag-chat-embed-window'
  panel.setAttribute('role', 'dialog')
  panel.setAttribute('aria-label', title)
  panel.style.cssText =
    'display:none;position:fixed;bottom:5.5rem;right:1.25rem;width:' +
    panelW +
    ';height:' +
    panelH +
    ';max-height:calc(100vh - 7rem);border-radius:16px;overflow:hidden;' +
    'box-shadow:0 12px 40px rgba(0,0,0,.18);z-index:2147483000;background:#fff;border:1px solid #e5e7eb'

  var iframe = document.createElement('iframe')
  iframe.src = iframeSrc
  iframe.title = title
  iframe.style.cssText = 'width:100%;height:100%;border:0;display:block'
  var allow = ['clipboard-read', 'clipboard-write']
  if (cfg.allowMicrophone !== false) allow.push('microphone')
  iframe.setAttribute('allow', allow.join('; '))

  panel.appendChild(iframe)
  root.appendChild(btn)
  root.appendChild(panel)

  var open = false
  function setOpen(v) {
    open = v
    panel.style.display = open ? 'block' : 'none'
    btn.setAttribute('aria-expanded', open ? 'true' : 'false')
  }
  btn.addEventListener('click', function (ev) {
    ev.stopPropagation()
    setOpen(!open)
  })
  document.addEventListener('click', function (ev) {
    if (!open) return
    var t = ev.target
    if (t && root.contains(t)) return
    setOpen(false)
  })
  panel.addEventListener('click', function (ev) {
    ev.stopPropagation()
  })
})()
