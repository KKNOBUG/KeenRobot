import dayjs from 'dayjs'

export function formatDateTime(time = undefined, format = 'YYYY-MM-DD HH:mm:ss') {
  return dayjs(time).format(format)
}

export function formatDate(date = undefined, format = 'YYYY-MM-DD') {
  return formatDateTime(date, format)
}

export function currentTimePeriod(regards = false) {
  const currentHour = new Date().getHours()
  if (currentHour >= 0 && currentHour < 6) return regards ? '凌晨啦' : '凌晨'
  if (currentHour >= 6 && currentHour < 9) return regards ? '早上好' : '早上'
  if (currentHour >= 9 && currentHour < 12) return regards ? '上午好' : '上午'
  if (currentHour >= 12 && currentHour < 13) return regards ? '中午好' : '中午'
  if (currentHour >= 13 && currentHour < 17) return regards ? '下午好' : '下午'
  if (currentHour >= 17 && currentHour < 20) return regards ? '傍晚好' : '傍晚'
  if (currentHour >= 20 && currentHour < 23) return regards ? '深夜啦' : '深夜'
  return regards ? '夜间啦' : '夜间'
}
