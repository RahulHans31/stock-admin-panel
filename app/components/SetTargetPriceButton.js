'use client';

import { useState, useRef, useEffect } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

export function SetTargetPriceButton({ id, currentTargetPrice, updateTargetPriceAction }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(currentTargetPrice != null ? String(currentTargetPrice) : '');
  const inputRef = useRef(null);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  async function handleSave() {
    await updateTargetPriceAction(id, value);
    setEditing(false);
    toast.success(value ? `Target price set to ₹${Number(value).toLocaleString('en-IN')}` : 'Target price cleared');
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter') handleSave();
    if (e.key === 'Escape') setEditing(false);
  }

  if (editing) {
    return (
      <div className="flex items-center gap-1.5">
        <div className="relative w-28">
          <span className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground text-xs">₹</span>
          <Input
            ref={inputRef}
            type="number"
            min="0"
            step="1"
            value={value}
            onChange={e => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="price"
            className="pl-5 h-7 text-xs"
          />
        </div>
        <Button size="sm" variant="default" className="h-7 px-2 text-xs" onClick={handleSave}>Save</Button>
        <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => setEditing(false)}>✕</Button>
      </div>
    );
  }

  return (
    <button
      onClick={() => setEditing(true)}
      className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors group"
      title="Set target price"
    >
      {currentTargetPrice != null ? (
        <span className="font-medium text-foreground/80">
          ₹{Number(currentTargetPrice).toLocaleString('en-IN')}
        </span>
      ) : (
        <span className="italic">—</span>
      )}
      <svg className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
      </svg>
    </button>
  );
}
