import { describe, expect, it } from 'vitest'

import { usePublications } from '../composables/usePublications'

/**
 * 成果发表页那两个拼串小工具。
 *
 * 它们错了都不会报错，只会**安静地把学术信息写错**：作者顺序被动过、机构角标指向别人的
 * 单位、出处一行少写一截卷期。这三样恰恰是读者拿去核对与引用的东西。
 *
 * `usePublications()` 不碰任何 Nuxt 运行时，可以直接 import 跑（同 manuscriptLines）。
 */
const { authorLine, citeLine } = usePublications()

describe('authorLine', () => {
  it('保持署名顺序，不排序不去重', () => {
    const authors = [
      { name: 'Wang Wu', affiliationIndex: 1 },
      { name: 'Zhang San', affiliationIndex: 0 },
      { name: 'Zhang San', affiliationIndex: 2 },
    ]

    expect(authorLine(authors)).toBe('Wang Wu, Zhang San, Zhang San')
  })

  it('超出上限写 et al.', () => {
    const authors = Array.from({ length: 12 }, (_, i) => ({ name: `A${i}`, affiliationIndex: null }))

    expect(authorLine(authors, 3)).toBe('A0, A1, A2, et al.')
  })

  it('刚好等于上限时不写 et al.', () => {
    const authors = [{ name: 'A', affiliationIndex: null }, { name: 'B', affiliationIndex: null }]

    expect(authorLine(authors, 2)).toBe('A, B')
  })

  it('没有作者时返回空串，让模板整行不渲染', () => {
    expect(authorLine([])).toBe('')
    expect(authorLine(null)).toBe('')
  })
})

describe('citeLine', () => {
  const base = {
    publicationId: 1,
    title: 'T',
    authors: null,
    affiliations: null,
    keywords: null,
    journal: null,
    volume: null,
    issue: null,
    pages: null,
    publicationYear: null,
    doi: null,
    sourceUrl: null,
    pdfUrl: null,
    coverImageUrl: null,
  }

  it('齐全时拼成 期刊, 卷(期):页, 年', () => {
    expect(citeLine({
      ...base,
      journal: 'Complementary Therapies in Medicine',
      volume: '80',
      issue: '3',
      pages: '145-152',
      publicationYear: 2024,
    })).toBe('Complementary Therapies in Medicine, 80(3):145-152, 2024')
  })

  it('缺卷期时不写空括号', () => {
    expect(citeLine({ ...base, journal: 'J', pages: '103041', publicationYear: 2023 })).toBe('J, 103041, 2023')
  })

  it('只有年份也成立（预印本、会议摘要没有期刊）', () => {
    expect(citeLine({ ...base, publicationYear: 2022 })).toBe('2022')
  })

  it('一个字段都没有时返回空串', () => {
    expect(citeLine(base)).toBe('')
    expect(citeLine(null)).toBe('')
  })
})
