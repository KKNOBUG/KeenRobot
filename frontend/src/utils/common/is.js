export function isNull(val) {
  return val === null
}

export function isUndef(val) {
  return typeof val === 'undefined'
}

export function isWhitespace(val) {
  return val === ''
}

export function isNullOrUndef(val) {
  return isNull(val) || isUndef(val)
}

export function isNullOrWhitespace(val) {
  return isNullOrUndef(val) || isWhitespace(val)
}

export function isExternal(path) {
  return /^(https?:|mailto:|tel:)/.test(path)
}
