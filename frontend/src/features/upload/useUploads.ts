import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useMemo, useRef, useState } from 'react';

import { documentKeys, fetchDocumentsById } from '../library/api';
import type { DocumentItem, UploadDetails } from '../library/types';
import { isTerminal } from '../library/types';
import { createPool, UPLOAD_CONCURRENCY } from './pool';
import { uploadFile } from './uploadFile';

/** How often the screen asks for the state of uploaded files (SYSTEM_DESIGN §5.1). */
export const POLL_MS = 1500;

/**
 * One file on the upload screen.
 *   waiting   queued in the browser (three upload at a time)
 *   uploading bytes on the way, with progress
 *   uploaded  the server accepted it; its processing status comes from polling
 *   rejected  the server refused the upload itself (type, size, duplicate)
 */
export interface UploadItem {
  key: string;
  file: File;
  phase: 'waiting' | 'uploading' | 'uploaded' | 'rejected';
  progress: number;
  document: DocumentItem | null;
  error: unknown;
}

interface UploadVariables {
  file: File;
  details: UploadDetails;
  onProgress: (fraction: number) => void;
}

/** The upload list, its three-at-a-time queue, and the status poll for uploaded files. */
export function useUploads() {
  const queryClient = useQueryClient();
  const [items, setItems] = useState<UploadItem[]>([]);
  const [pool] = useState(() => createPool(UPLOAD_CONCURRENCY));
  const nextKey = useRef(0);

  // A mutation, so a 401 ends the session like any other request (app/queryClient.ts).
  const upload = useMutation({
    mutationFn: ({ file, details, onProgress }: UploadVariables) =>
      uploadFile(file, details, { onProgress }),
    // The variables hold the File: don't keep them once the upload has settled.
    gcTime: 0,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...documentKeys.all, 'list'] });
    },
  });
  const { mutateAsync } = upload;

  const patch = useCallback((key: string, change: Partial<UploadItem>) => {
    setItems((current) =>
      current.map((item) => (item.key === key ? { ...item, ...change } : item)),
    );
  }, []);

  const addFiles = useCallback(
    (files: readonly File[], details: UploadDetails) => {
      const added = files.map((file): UploadItem => {
        nextKey.current += 1;
        return {
          key: `upload-${String(nextKey.current)}`,
          file,
          phase: 'waiting',
          progress: 0,
          document: null,
          error: null,
        };
      });
      setItems((current) => [...current, ...added]);
      for (const item of added) {
        pool.add(async () => {
          patch(item.key, { phase: 'uploading' });
          try {
            const document = await mutateAsync({
              file: item.file,
              details,
              onProgress: (progress) => {
                patch(item.key, { progress });
              },
            });
            patch(item.key, { phase: 'uploaded', progress: 1, document });
          } catch (error) {
            patch(item.key, { phase: 'rejected', error });
          }
        });
      }
    },
    [mutateAsync, patch, pool],
  );

  const ids = useMemo(
    () => items.flatMap((item) => (item.document ? [item.document.id] : [])),
    [items],
  );
  const status = useQuery({
    queryKey: documentKeys.status(ids),
    queryFn: ({ signal }) => fetchDocumentsById(ids, signal),
    enabled: ids.length > 0,
    // Rows keep their last known state while the next poll (with a new file) is on its way.
    placeholderData: keepPreviousData,
    // Every POLL_MS until each uploaded file is ready or failed. A document the poll no longer
    // returns (archived and filtered, say) counts as settled, so polling always ends.
    refetchInterval: (query) => {
      const latest = new Map(query.state.data?.map((doc) => [doc.id, doc]));
      const settled = ids.every((id) => {
        const doc = latest.get(id);
        return query.state.data !== undefined && (!doc || isTerminal(doc.status));
      });
      return settled ? false : POLL_MS;
    },
  });

  const rows = useMemo(() => {
    const latest = new Map(status.data?.map((doc) => [doc.id, doc]));
    return items.map((item) =>
      item.document ? { ...item, document: latest.get(item.document.id) ?? item.document } : item,
    );
  }, [items, status.data]);

  return { rows, addFiles };
}
