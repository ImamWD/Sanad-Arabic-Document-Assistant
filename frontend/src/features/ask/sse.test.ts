import { describe, expect, it } from 'vitest';

import { createSseParser, type SseMessage } from './sse';

function parse(...chunks: string[]): SseMessage[] {
  const messages: SseMessage[] = [];
  const parser = createSseParser((message) => messages.push(message));
  for (const chunk of chunks) parser.push(chunk);
  return messages;
}

describe('createSseParser', () => {
  it('reads named events with JSON data', () => {
    expect(
      parse('event: stage\ndata: {"stage":"searching"}\n\nevent: token\ndata: {"text":"ا"}\n\n'),
    ).toEqual([
      { event: 'stage', data: '{"stage":"searching"}' },
      { event: 'token', data: '{"text":"ا"}' },
    ]);
  });

  it('joins events split anywhere across chunks', () => {
    const text = 'event: eta\ndata: {"expected_seconds": 45}\n\n';
    for (let cut = 1; cut < text.length; cut++) {
      expect(parse(text.slice(0, cut), text.slice(cut))).toEqual([
        { event: 'eta', data: '{"expected_seconds": 45}' },
      ]);
    }
  });

  it('accepts CRLF and CR line endings, including a CRLF split between chunks', () => {
    // A trailing CR could be half of a CRLF, so the next chunk (here a ping) completes it.
    expect(parse('event: a\r\ndata: 1\r\n\r\nevent: b\rdata: 2\r\r', ': ping\n')).toEqual([
      { event: 'a', data: '1' },
      { event: 'b', data: '2' },
    ]);
    expect(parse('event: a\r', '\ndata: 1\r', '\n\r', '\n')).toEqual([{ event: 'a', data: '1' }]);
  });

  it('joins multi-line data with newlines', () => {
    expect(parse('data: first\ndata: second\n\n')).toEqual([
      { event: 'message', data: 'first\nsecond' },
    ]);
  });

  it('skips comments such as the keep-alive ping', () => {
    expect(parse(': ping\n\n: ping\nevent: stage\ndata: {}\n\n')).toEqual([
      { event: 'stage', data: '{}' },
    ]);
  });

  it('keeps a value without the optional leading space, and ignores id and retry', () => {
    expect(parse('id: 7\nretry: 1000\nevent:token\ndata:{"text":" x"}\n\n')).toEqual([
      { event: 'token', data: '{"text":" x"}' },
    ]);
  });

  it('never dispatches a message the stream cut off before its blank line', () => {
    expect(parse('event: final\ndata: {"outcome":"answered"}\n')).toEqual([]);
  });

  it('dispatches nothing for an event line without data', () => {
    expect(parse('event: stage\n\n')).toEqual([]);
  });
});
