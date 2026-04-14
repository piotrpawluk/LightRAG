import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import Button from '@/components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import {
  uploadToolFile,
  createTool,
  listTools,
  deleteTool,
  type ToolDef,
  type ToolParameterDef,
  type UploadToolFileResponse,
} from '@/api/lightrag'
import { UploadIcon, TrashIcon, WrenchIcon, PlusIcon, XIcon } from 'lucide-react'

interface ParamFormEntry {
  column_name: string
  param_name: string
  param_description: string
  selected: boolean
}

export default function ExcelTools() {
  const { t } = useTranslation()
  const [tools, setTools] = useState<ToolDef[]>([])
  const [loading, setLoading] = useState(false)

  // Upload flow state
  const [uploadResult, setUploadResult] = useState<UploadToolFileResponse | null>(null)
  const [paramEntries, setParamEntries] = useState<ParamFormEntry[]>([])
  const [toolName, setToolName] = useState('')
  const [toolDescription, setToolDescription] = useState('')
  const [creating, setCreating] = useState(false)

  const fetchTools = useCallback(async () => {
    try {
      const res = await listTools()
      setTools(res.tools || [])
    } catch (e: any) {
      console.error('Failed to fetch tools:', e)
    }
  }, [])

  useEffect(() => {
    fetchTools()
  }, [fetchTools])

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (!file.name.toLowerCase().endsWith('.xlsx') && !file.name.toLowerCase().endsWith('.xls')) {
      toast.error('Invalid file format. Please upload an .xlsx or .xls file.')
      return
    }

    setLoading(true)
    try {
      const result = await uploadToolFile(file)
      setUploadResult(result)
      setParamEntries(
        result.columns.map((col) => ({
          column_name: col,
          param_name: col.toLowerCase().replace(/\s+/g, '_'),
          param_description: '',
          selected: false,
        }))
      )
      setToolName('')
      setToolDescription('')
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Failed to upload file')
    } finally {
      setLoading(false)
      e.target.value = ''
    }
  }

  const handleCreate = async () => {
    if (!uploadResult) return
    if (!toolName.trim()) {
      toast.error('Tool name is required')
      return
    }
    if (!toolDescription.trim()) {
      toast.error('Tool description is required')
      return
    }

    const selectedParams = paramEntries.filter((p) => p.selected)
    if (selectedParams.length === 0) {
      toast.error('Select at least one search-by column')
      return
    }

    const params: ToolParameterDef[] = selectedParams.map((p) => ({
      column_name: p.column_name,
      param_name: p.param_name,
      param_description: p.param_description,
    }))

    setCreating(true)
    try {
      await createTool({
        file_id: uploadResult.file_id,
        name: toolName.trim(),
        description: toolDescription.trim(),
        parameters: params,
      })
      toast.success(`Tool "${toolName}" created successfully`)
      setUploadResult(null)
      setParamEntries([])
      setToolName('')
      setToolDescription('')
      await fetchTools()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Failed to create tool')
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (tool: ToolDef) => {
    if (!confirm(`Delete tool "${tool.name}"?`)) return
    try {
      await deleteTool(tool.tool_id)
      toast.success(`Tool "${tool.name}" deleted`)
      await fetchTools()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Failed to delete tool')
    }
  }

  const cancelUpload = () => {
    setUploadResult(null)
    setParamEntries([])
    setToolName('')
    setToolDescription('')
  }

  const toggleColumn = (index: number) => {
    setParamEntries((prev) =>
      prev.map((p, i) => (i === index ? { ...p, selected: !p.selected } : p))
    )
  }

  const updateParamField = (index: number, field: 'param_name' | 'param_description', value: string) => {
    setParamEntries((prev) =>
      prev.map((p, i) => (i === index ? { ...p, [field]: value } : p))
    )
  }

  return (
    <div className="container mx-auto max-w-4xl p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <WrenchIcon className="size-6" />
            {t('header.tools', 'Tools')}
          </h1>
          <p className="text-muted-foreground text-sm mt-1">
            Upload Excel files and register them as LLM-callable tools
          </p>
        </div>
        {!uploadResult && (
          <label>
            <input
              type="file"
              accept=".xlsx,.xls"
              className="hidden"
              onChange={handleFileUpload}
              disabled={loading}
            />
            <Button asChild variant="default" disabled={loading}>
              <span className="cursor-pointer">
                <UploadIcon className="size-4 mr-2" />
                {loading ? 'Uploading...' : 'Upload Excel'}
              </span>
            </Button>
          </label>
        )}
      </div>

      {/* Create Tool Form (shown after upload) */}
      {uploadResult && (
        <Card>
          <CardHeader>
            <div className="flex justify-between items-center">
              <div>
                <CardTitle>Create Tool</CardTitle>
                <CardDescription>
                  {uploadResult.row_count} rows, {uploadResult.columns.length} columns detected
                </CardDescription>
              </div>
              <Button variant="ghost" size="icon" onClick={cancelUpload}>
                <XIcon className="size-4" />
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Tool name */}
            <div>
              <label className="text-sm font-medium block mb-1">Tool Name</label>
              <input
                type="text"
                className="w-full rounded-md border px-3 py-2 text-sm bg-background"
                placeholder="e.g. product-lookup"
                value={toolName}
                onChange={(e) => setToolName(e.target.value)}
              />
            </div>

            {/* Tool description */}
            <div>
              <label className="text-sm font-medium block mb-1">Tool Description</label>
              <textarea
                className="w-full rounded-md border px-3 py-2 text-sm bg-background min-h-[60px]"
                placeholder="Describe what this tool does for the LLM..."
                value={toolDescription}
                onChange={(e) => setToolDescription(e.target.value)}
              />
            </div>

            {/* Column selection */}
            <div>
              <label className="text-sm font-medium block mb-2">
                Select Search-By Columns
              </label>
              <div className="space-y-3 max-h-[300px] overflow-auto">
                {paramEntries.map((entry, idx) => (
                  <div key={entry.column_name} className="border rounded-md p-3">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={entry.selected}
                        onChange={() => toggleColumn(idx)}
                        className="rounded"
                      />
                      <span className="font-medium text-sm">{entry.column_name}</span>
                    </label>
                    {entry.selected && (
                      <div className="mt-2 ml-6 space-y-2">
                        <div>
                          <label className="text-xs text-muted-foreground block mb-1">
                            Parameter Name
                          </label>
                          <input
                            type="text"
                            className="w-full rounded border px-2 py-1 text-sm bg-background"
                            value={entry.param_name}
                            onChange={(e) => updateParamField(idx, 'param_name', e.target.value)}
                          />
                        </div>
                        <div>
                          <label className="text-xs text-muted-foreground block mb-1">
                            Parameter Description
                          </label>
                          <input
                            type="text"
                            className="w-full rounded border px-2 py-1 text-sm bg-background"
                            placeholder="Describe this parameter for the LLM..."
                            value={entry.param_description}
                            onChange={(e) =>
                              updateParamField(idx, 'param_description', e.target.value)
                            }
                          />
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Create button */}
            <div className="flex justify-end">
              <Button onClick={handleCreate} disabled={creating}>
                <PlusIcon className="size-4 mr-2" />
                {creating ? 'Creating...' : 'Create Tool'}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tools List */}
      {tools.length === 0 && !uploadResult ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <WrenchIcon className="size-12 mx-auto mb-4 opacity-30" />
            <p>No tools registered yet.</p>
            <p className="text-sm mt-1">Upload an Excel file to create your first tool.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {tools.map((tool) => (
            <Card key={tool.tool_id}>
              <CardContent className="py-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold">{tool.name}</h3>
                      <span className="text-xs bg-muted px-2 py-0.5 rounded">
                        {tool.row_count} rows
                      </span>
                      <span className="text-xs bg-muted px-2 py-0.5 rounded">
                        {tool.parameters?.length || 0} params
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground mt-1">{tool.description}</p>
                    {tool.parameters && tool.parameters.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {tool.parameters.map((p) => (
                          <span
                            key={p.param_name}
                            className="text-xs border rounded px-2 py-0.5"
                          >
                            {p.param_name}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleDelete(tool)}
                    className="text-destructive hover:text-destructive"
                  >
                    <TrashIcon className="size-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
