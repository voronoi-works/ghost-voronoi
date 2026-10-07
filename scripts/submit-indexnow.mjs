import fs from 'node:fs'
import path from 'node:path'

const HOST = 'ghost.voronoi.works'
const KEY = '94d91677157b448291e13a43454ed8c2'
const KEY_LOCATION = `https://${HOST}/${KEY}.txt`

async function getUrlList() {
  const urls = new Set([
    `https://${HOST}/`,
    `https://${HOST}/theory`,
    `https://${HOST}/theory/distributed-self`,
    `https://${HOST}/theory/dcgu`,
    `https://${HOST}/theory/subject-range`,
    `https://${HOST}/theory/external-subject`,
    `https://${HOST}/theory/attachment`,
    `https://${HOST}/theory/jean-denim`,
  ])

  let sitemapContent = null
  const sitemapPath = path.resolve('public/sitemap.xml')

  if (fs.existsSync(sitemapPath)) {
    console.log('[IndexNow] Reading sitemap from local public/sitemap.xml')
    sitemapContent = fs.readFileSync(sitemapPath, 'utf-8')
  } else {
    console.log(`[IndexNow] Local sitemap not found. Fetching remote sitemap from https://${HOST}/sitemap.xml...`)
    try {
      const res = await fetch(`https://${HOST}/sitemap.xml`)
      if (res.ok) {
        sitemapContent = await res.text()
      } else {
        console.warn(`[IndexNow] Failed to fetch remote sitemap: ${res.status} ${res.statusText}`)
      }
    } catch (e) {
      console.warn(`[IndexNow] Error fetching remote sitemap:`, e.message)
    }
  }

  if (sitemapContent) {
    const matches = sitemapContent.match(/<loc>(https:\/\/[^<]+)<\/loc>/g)
    if (matches) {
      for (const m of matches) {
        const url = m.replace(/<\/?loc>/g, '').trim()
        urls.add(url)
      }
    }
  }

  return Array.from(urls)
}

async function main() {
  const urlList = await getUrlList()
  console.log(`[IndexNow] Submitting ${urlList.length} URLs for host: ${HOST}...`)

  const payload = {
    host: HOST,
    key: KEY,
    keyLocation: KEY_LOCATION,
    urlList,
  }

  const endpoints = [
    'https://api.indexnow.org/indexnow',
    'https://www.bing.com/indexnow',
  ]

  let success = false

  for (const endpoint of endpoints) {
    try {
      console.log(`[IndexNow] Sending request to ${endpoint}...`)
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
        },
        body: JSON.stringify(payload),
      })
      console.log(`[IndexNow] Response from ${endpoint}: ${res.status} ${res.statusText}`)
      if (res.status === 200 || res.status === 202) {
        console.log(`[IndexNow] SUCCESS! URLs successfully accepted by ${endpoint}.`)
        success = true
        break
      } else {
        const text = await res.text()
        console.warn(`[IndexNow] Non-success response from ${endpoint}: ${text}`)
      }
    } catch (err) {
      console.error(`[IndexNow] Error submitting to ${endpoint}:`, err.message)
    }
  }

  if (!success) {
    console.error('[IndexNow] FAILED to submit URLs to all IndexNow endpoints.')
    process.exitCode = 1
  }
}

main()
