import { useEffect } from 'react';
export const useUnsavedGuard = dirty => {
  useEffect(() => {
    if (!dirty) return;
    const leave = e => { e.preventDefault(); e.returnValue = ''; };
    const navigate = e => {
      const link = e.target.closest?.('a[href]');
      if (!link || link.target === '_blank' || link.href === window.location.href) return;
      if (!window.confirm('Perubahan belum disimpan. Tetap meninggalkan halaman ini?')) { e.preventDefault(); e.stopPropagation(); }
    };
    window.addEventListener('beforeunload', leave);
    document.addEventListener('click', navigate, true);
    return () => { window.removeEventListener('beforeunload', leave); document.removeEventListener('click', navigate, true); };
  }, [dirty]);
};