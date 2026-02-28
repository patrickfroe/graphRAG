export const SOURCE_ITEM_SELECTOR = '[data-source-id]';

/**
 * Scrolls the sources panel to a source row by its id (for example "S3").
 *
 * The sources panel can be any ancestor that contains elements with `data-source-id`.
 */
export function scrollSourcesPanelToSource(sourceId: string, root: ParentNode = document): boolean {
  const escapedId = typeof CSS !== 'undefined' && CSS.escape ? CSS.escape(sourceId) : sourceId;
  const target = root.querySelector<HTMLElement>(`[data-source-id="${escapedId}"]`);

  if (!target) {
    return false;
  }

  target.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
  target.focus?.({ preventScroll: true });
  return true;
}
