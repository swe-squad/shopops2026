import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { ArtifactDownload } from './artifact-download'
const artifact = {id:'artifact-1',filename:'report.md',media_type:'text/markdown' as const,size:2,sha256:'565339bc4d33d72817b583024112eb7f5cdf3e5eef0252d6ec1b9c9a94e12bb3',availability:'available' as const}
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks()})
it('downloads with authorization and revokes its blob URL without navigation or chat input',async()=>{
  const create=vi.fn(()=> 'blob:report'),revoke=vi.fn(),click=vi.spyOn(HTMLAnchorElement.prototype,'click').mockImplementation(()=>{})
  vi.stubGlobal('URL',class extends URL {static createObjectURL=create;static revokeObjectURL=revoke})
  const fetcher=vi.fn().mockResolvedValue(new Response('OK',{headers:{'Content-Type':'text/markdown'}}))
  vi.stubGlobal('fetch',fetcher)
  render(<ArtifactDownload token="session" artifact={artifact}/>)
  fireEvent.click(screen.getByRole('button',{name:'Download report.md'}))
  await vi.waitFor(()=>expect(revoke).toHaveBeenCalledWith('blob:report'))
  expect(click).toHaveBeenCalledOnce()
  expect(fetcher).toHaveBeenCalledOnce()
  expect(fetcher).toHaveBeenCalledWith('/api/chat/artifacts/artifact-1/content',expect.objectContaining({headers:{Authorization:'Bearer session'},redirect:'error'}))
})
it('keeps an expired report visible and permits only download retry',async()=>{
  const fetcher=vi.fn().mockResolvedValue(new Response(null,{status:410}))
  vi.stubGlobal('fetch',fetcher)
  render(<ArtifactDownload token="session" artifact={artifact}/>)
  fireEvent.click(screen.getByRole('button',{name:'Download report.md'}))
  expect(await screen.findByRole('alert')).toHaveTextContent('no longer available')
  expect(screen.getByRole('button',{name:'Download report.md'})).toBeEnabled()
  expect(fetcher).toHaveBeenCalledOnce()
})
