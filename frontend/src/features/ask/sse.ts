// A text/event-stream parser (the WHATWG "server-sent events" format). EventSource can only
// GET, and the question is POSTed, so the stream is read with fetch and parsed here.

export interface SseMessage {
  event: string;
  data: string;
}

export interface SseParser {
  /** Feed decoded text. Chunks may split lines and line endings anywhere. */
  push(text: string): void;
}

/**
 * Calls `onMessage` for every complete message. Lines end with LF, CR or CRLF; a blank line
 * ends a message; `:` lines are comments (the server's `: ping` keep-alive). A message cut off
 * by the end of the stream is never dispatched, as the format requires.
 */
export function createSseParser(onMessage: (message: SseMessage) => void): SseParser {
  let buffer = '';
  let event = '';
  let data: string[] = [];

  function line(text: string) {
    if (text === '') {
      if (data.length > 0) onMessage({ event: event || 'message', data: data.join('\n') });
      event = '';
      data = [];
      return;
    }
    if (text.startsWith(':')) return;
    const colon = text.indexOf(':');
    const field = colon === -1 ? text : text.slice(0, colon);
    let value = colon === -1 ? '' : text.slice(colon + 1);
    if (value.startsWith(' ')) value = value.slice(1);
    if (field === 'event') event = value;
    else if (field === 'data') data.push(value);
    // `id` and `retry` only matter to EventSource reconnection, which a POST never does.
  }

  return {
    push(text) {
      buffer += text;
      let start = 0;
      for (let i = 0; i < buffer.length; i++) {
        const char = buffer[i];
        if (char !== '\n' && char !== '\r') continue;
        // A CR at the very end may be the first half of a CRLF: wait for the next chunk.
        if (char === '\r' && i === buffer.length - 1) break;
        line(buffer.slice(start, i));
        if (char === '\r' && buffer[i + 1] === '\n') i++;
        start = i + 1;
      }
      buffer = buffer.slice(start);
    },
  };
}
