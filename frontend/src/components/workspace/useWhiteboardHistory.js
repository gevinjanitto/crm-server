import { useCallback, useState } from 'react';

const empty = { nodes: [], edges: [] };
export const useWhiteboardHistory = () => {
  const [state, setState] = useState({ present: empty, past: [], future: [], dirty: false });
  const reset = useCallback(present => setState({ present, past: [], future: [], dirty: false }), []);
  const update = useCallback((change, { remember = true, dirty = true } = {}) => {
    setState(previous => {
      const present = change(previous.present);
      if (present === previous.present) return previous;
      return {
        present, dirty: previous.dirty || dirty,
        past: remember ? [...previous.past.slice(-49), previous.present] : previous.past,
        future: dirty ? [] : previous.future,
      };
    });
  }, []);
  const checkpoint = useCallback(() => setState(previous => ({
    ...previous, past: [...previous.past.slice(-49), previous.present], future: [],
  })), []);
  const undo = useCallback(() => setState(previous => previous.past.length ? {
    present: previous.past.at(-1), past: previous.past.slice(0, -1),
    future: [previous.present, ...previous.future], dirty: true,
  } : previous), []);
  const redo = useCallback(() => setState(previous => previous.future.length ? {
    present: previous.future[0], past: [...previous.past, previous.present],
    future: previous.future.slice(1), dirty: true,
  } : previous), []);
  const markSaved = useCallback(() => setState(previous => ({ ...previous, dirty: false })), []);
  return { ...state.present, dirty: state.dirty, canUndo: !!state.past.length, canRedo: !!state.future.length,
    reset, update, checkpoint, undo, redo, markSaved };
};