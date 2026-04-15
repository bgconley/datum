import { useEffect, useState } from 'react'

import type { DatumNotificationDetail } from '@/lib/notifications'

interface ToastMessage {
  id: number
  message: string
}

export function NotificationCenter() {
  const [messages, setMessages] = useState<ToastMessage[]>([])

  useEffect(() => {
    const handleNotification = (event: Event) => {
      const detail = (event as CustomEvent<DatumNotificationDetail>).detail
      if (!detail?.message) {
        return
      }

      const id = Date.now() + Math.floor(Math.random() * 1000)
      setMessages((current) => [...current, { id, message: detail.message }])
      window.setTimeout(() => {
        setMessages((current) => current.filter((message) => message.id !== id))
      }, 4000)
    }

    window.addEventListener('datum:notify', handleNotification)
    return () => window.removeEventListener('datum:notify', handleNotification)
  }, [])

  if (messages.length === 0) {
    return null
  }

  return (
    <div className="pointer-events-none fixed right-4 top-4 z-50 flex w-full max-w-sm flex-col gap-2">
      {messages.map((message) => (
        <div
          key={message.id}
          className="rounded-2xl border border-border/80 bg-card/95 px-4 py-3 text-sm text-foreground shadow-lg backdrop-blur"
        >
          {message.message}
        </div>
      ))}
    </div>
  )
}
