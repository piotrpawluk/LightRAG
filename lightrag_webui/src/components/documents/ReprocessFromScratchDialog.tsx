import { useState, useCallback, useEffect } from 'react'
import Button from '@/components/ui/Button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter
} from '@/components/ui/Dialog'
import Input from '@/components/ui/Input'
import { toast } from 'sonner'
import { errorMessage } from '@/lib/utils'
import { reprocessFailedDocuments } from '@/api/lightrag'

import { RotateCcwIcon, AlertTriangleIcon } from 'lucide-react'
import { useTranslation } from 'react-i18next'

const Label = ({
  htmlFor,
  className,
  children,
  ...props
}: React.LabelHTMLAttributes<HTMLLabelElement>) => (
  <label htmlFor={htmlFor} className={className} {...props}>
    {children}
  </label>
)

interface ReprocessFromScratchDialogProps {
  selectedDocIds: string[]
  onReprocessStarted?: () => Promise<void>
}

export default function ReprocessFromScratchDialog({
  selectedDocIds,
  onReprocessStarted
}: ReprocessFromScratchDialogProps) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [confirmText, setConfirmText] = useState('')
  const [isReprocessing, setIsReprocessing] = useState(false)
  const isConfirmEnabled = confirmText.toLowerCase() === 'yes' && !isReprocessing

  useEffect(() => {
    if (!open) {
      setConfirmText('')
      setIsReprocessing(false)
    }
  }, [open])

  const handleReprocess = useCallback(async () => {
    if (!isConfirmEnabled || selectedDocIds.length === 0) return

    setIsReprocessing(true)
    try {
      const result = await reprocessFailedDocuments({
        documentIds: selectedDocIds,
        fromScratch: true
      })

      if (result.status === 'reprocessing_started') {
        toast.success(
          t('documentPanel.reprocessFromScratch.success', { count: selectedDocIds.length })
        )
      } else {
        toast.error(
          t('documentPanel.reprocessFromScratch.failed', { message: result.message })
        )
        setConfirmText('')
        setIsReprocessing(false)
        return
      }

      if (onReprocessStarted) {
        onReprocessStarted().catch(console.error)
      }
      setOpen(false)
    } catch (err) {
      toast.error(t('documentPanel.reprocessFromScratch.error', { error: errorMessage(err) }))
      setConfirmText('')
    } finally {
      setIsReprocessing(false)
    }
  }, [isConfirmEnabled, selectedDocIds, setOpen, t, onReprocessStarted])

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          variant="outline"
          side="bottom"
          tooltip={t('documentPanel.reprocessFromScratch.tooltip', { count: selectedDocIds.length })}
          size="sm"
        >
          <RotateCcwIcon /> {t('documentPanel.reprocessFromScratch.button')}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-xl" onCloseAutoFocus={(e) => e.preventDefault()}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-amber-600 dark:text-amber-400 font-bold">
            <AlertTriangleIcon className="h-5 w-5" />
            {t('documentPanel.reprocessFromScratch.title', { count: selectedDocIds.length })}
          </DialogTitle>
          <DialogDescription className="pt-2">
            {t('documentPanel.reprocessFromScratch.description', { count: selectedDocIds.length })}
          </DialogDescription>
        </DialogHeader>

        <div className="text-amber-600 dark:text-amber-400 font-semibold mb-4">
          {t('documentPanel.reprocessFromScratch.warning')}
        </div>

        <div className="space-y-2">
          <Label htmlFor="reprocess-confirm-text" className="text-sm font-medium">
            {t('documentPanel.reprocessFromScratch.confirmPrompt')}
          </Label>
          <Input
            id="reprocess-confirm-text"
            value={confirmText}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setConfirmText(e.target.value)}
            placeholder={t('documentPanel.reprocessFromScratch.confirmPlaceholder')}
            className="w-full"
            disabled={isReprocessing}
          />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)} disabled={isReprocessing}>
            {t('common.cancel')}
          </Button>
          <Button onClick={handleReprocess} disabled={!isConfirmEnabled}>
            {isReprocessing
              ? t('documentPanel.reprocessFromScratch.reprocessing')
              : t('documentPanel.reprocessFromScratch.confirmButton')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
