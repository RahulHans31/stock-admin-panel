'use client';

import { useRef, useState } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

export function AddProductForm({ addProductAction }) {
  const formRef = useRef(null);
  const [url, setUrl] = useState('');
  const showPartNumber = url.includes('apple.com');

  async function formAction(formData) {
    const result = await addProductAction(formData);
    
    if (result?.error) {
      toast.error(result.error);
    } else {
      toast.success("Product added to tracker!");
      formRef.current?.reset();
      setUrl('');
    }
  }

  return (
    <form ref={formRef} action={formAction} className="flex flex-col w-full space-y-3">
      <div className="flex w-full items-center space-x-2">
        <Input
          type="text"
          name="url"
          // --- UPDATED PLACEHOLDER ---
          placeholder="Paste Croma, Apple, Amazon, Flipkart, iQOO, or Vivo URL"
          required
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <Button type="submit">Add Product</Button>
      </div>
      
      {showPartNumber && (
        <Input
          type="text"
          name="partNumber"
          placeholder="Apple Part Number (e.g., MG6P4HN/A)"
          required
          className="transition-all duration-300"
        />
      )}

      <Input
        type="text"
        name="affiliateLink"
        placeholder="Your Affiliate Link (Optional)"
      />
    </form>
  );
}