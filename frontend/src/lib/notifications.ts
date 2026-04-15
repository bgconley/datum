export interface DatumNotificationDetail {
  message: string
}

export function notify(message: string) {
  if (typeof window === 'undefined') {
    return
  }

  window.dispatchEvent(
    new CustomEvent<DatumNotificationDetail>('datum:notify', {
      detail: { message },
    }),
  )
}
