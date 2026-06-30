import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { isLikelyHtmlPayload } from './isLikelyHtmlResponse'

describe('isLikelyHtmlPayload', () => {
  it('detects SPA index.html payloads', () => {
    assert.equal(isLikelyHtmlPayload('<!doctype html><html><head></head></html>'), true)
    assert.equal(isLikelyHtmlPayload('  <html lang="zh-CN">'), true)
  })

  it('ignores json and objects', () => {
    assert.equal(isLikelyHtmlPayload('[]'), false)
    assert.equal(isLikelyHtmlPayload('{"items":[]}'), false)
    assert.equal(isLikelyHtmlPayload({ items: [] }), false)
  })
})
