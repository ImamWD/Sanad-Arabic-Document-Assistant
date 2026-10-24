import { useMutation, useQueryClient } from '@tanstack/react-query';

import { documentKeys, type LifecycleAction, runLifecycle, updateDocument } from './api';
import type { DocumentItem, DocumentPatch } from './types';

/** Store a changed document and refresh every list that may show it. */
function useStoreDocument() {
  const queryClient = useQueryClient();
  return (document: DocumentItem) => {
    queryClient.setQueryData(documentKeys.detail(document.id), document);
    void queryClient.invalidateQueries({ queryKey: [...documentKeys.all, 'list'] });
  };
}

/** Archive, unarchive, retry, and the restricted flag (editor+; the server checks the role). */
export function useLifecycle() {
  const store = useStoreDocument();
  return useMutation({
    mutationFn: ({
      id,
      action,
    }: {
      id: string;
      action: LifecycleAction | 'restrict' | 'unrestrict';
    }) =>
      action === 'restrict' || action === 'unrestrict'
        ? updateDocument(id, { restricted: action === 'restrict' })
        : runLifecycle(id, action),
    onSuccess: store,
  });
}

/** Save edited metadata. Only the changed fields are sent. */
export function useUpdateDocument() {
  const store = useStoreDocument();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: DocumentPatch }) => updateDocument(id, patch),
    onSuccess: store,
  });
}
