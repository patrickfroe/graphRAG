import React, { Fragment, ReactNode, useMemo } from 'react';
import { scrollSourcesPanelToSource } from '../utils/sourcesPanel';

const CITATION_REGEX = /\[(S\d+)\]/g;

export type CitationsRendererProps = {
  answer: string;
  className?: string;
  onCitationClick?: (sourceId: string) => void;
  /**
   * Optional root node used to find source elements with [data-source-id="Sx"].
   * Defaults to document.
   */
  sourcesRoot?: ParentNode;
};

function parseAnswer(answer: string): Array<string | { sourceId: string }> {
  const segments: Array<string | { sourceId: string }> = [];
  let lastIndex = 0;

  for (const match of answer.matchAll(CITATION_REGEX)) {
    const fullMatch = match[0];
    const sourceId = match[1];
    const start = match.index ?? 0;

    if (start > lastIndex) {
      segments.push(answer.slice(lastIndex, start));
    }

    segments.push({ sourceId });
    lastIndex = start + fullMatch.length;
  }

  if (lastIndex < answer.length) {
    segments.push(answer.slice(lastIndex));
  }

  return segments;
}

export function CitationsRenderer({
  answer,
  className,
  onCitationClick,
  sourcesRoot,
}: CitationsRendererProps) {
  const segments = useMemo(() => parseAnswer(answer), [answer]);

  const content: ReactNode[] = segments.map((segment, index) => {
    if (typeof segment === 'string') {
      return <Fragment key={`text-${index}`}>{segment}</Fragment>;
    }

    const { sourceId } = segment;

    return (
      <button
        key={`${sourceId}-${index}`}
        type="button"
        className="citation"
        onClick={() => {
          onCitationClick?.(sourceId);
          scrollSourcesPanelToSource(sourceId, sourcesRoot ?? document);
        }}
        aria-label={`Jump to source ${sourceId}`}
      >
        [{sourceId}]
      </button>
    );
  });

  return <span className={className}>{content}</span>;
}

export { parseAnswer, CITATION_REGEX };
