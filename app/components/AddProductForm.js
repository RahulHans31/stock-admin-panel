'use client';

import { useRef, useState, useEffect } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

/**
 * Extracts the Apple Part Number from an Apple product URL.
 * It uses a more flexible regex to capture the part number, 
 * which is typically found after '/product/'.
 * @param {string} url 
 * @returns {string | null} The part number or null if not found.
 */
function extractApplePartNumber(url) {
  // FIXED REGEX: Matches /product/ followed by one or more characters that are NOT a slash or a question mark.
  // This handles URLs like:
  // - /product/MG6P4HN/A/some-name
  // - /product/MG6P4HN/A?cid=...
  // - /product/MG6P4HN/A (at the end of the path)
  const match = url.match(/\/product\/([^/?]+)/i);
  if (match && match[1]) {
    // Return the captured group, which is the part number
    return match[1]; 
  }
  return null;
}

/**
 * Derives the storeType and checks if productId (Part Number) should be shown,
 * and extracts the part number if possible.
 * @param {string} url 
 * @returns {object} { storeType, showPartNumber, extractedPartNumber }
 */
function getStoreDetails(url) {
  const lowerUrl = url.toLowerCase();
  
  if (lowerUrl.includes('apple.com')) {
    const partNumber = extractApplePartNumber(lowerUrl);
    return { storeType: 'unicorn', showPartNumber: true, extractedPartNumber: partNumber };
  }
  if (lowerUrl.includes('reliancedigital.in')) {
    return { storeType: 'reliance_digital', showPartNumber: false, extractedPartNumber: null };
  }
  if (lowerUrl.includes('iqoo.com')) {
    return { storeType: 'iqoo', showPartNumber: false, extractedPartNumber: null };
  }
  if (lowerUrl.includes('vivo.com')) {
    return { storeType: 'vivo', showPartNumber: false, extractedPartNumber: null };
  }
  // For Croma or Flipkart/Amazon, we generally need the explicit ID for API lookups.
  if (lowerUrl.includes('croma.com') || lowerUrl.includes('flipkart.com') || lowerUrl.includes('amazon.in')) {
    return { storeType: 'unknown', showPartNumber: true, extractedPartNumber: null }; 
  }

  // Default fallback or general case
  return { storeType: 'unknown', showPartNumber: false, extractedPartNumber: null };
}


export function AddProductForm({ addProductAction }) {
  const formRef = useRef(null);
  const [url, setUrl] = useState('');
  // New state to hold the product ID/part number
  const [productId, setProductId] = useState(''); 
  
  // Use the derived details
  const { storeType, showPartNumber, extractedPartNumber } = getStoreDetails(url);

  // --- NEW useEffect hook to handle auto-population ---
  useEffect(() => {
    // 1. If a part number was successfully extracted, set it. This auto-fills for Apple.
    if (extractedPartNumber) {
      setProductId(extractedPartNumber);
      // Exit early to prevent other rules from running
      return; 
    }
    
    // 2. If the URL field is empty (user cleared it), clear the Part ID field.
    if (!url) {
        setProductId('');
        return;
    }
    
    // 3. If the field is shown but it's NOT an Apple store (i.e., Croma/Flipkart/Amazon), 
    //    we should NOT clear the productId, as the user might be manually typing it in.
    //    We only clear it if the input field is now supposed to be hidden entirely.
    if (!showPartNumber) {
      setProductId('');
    }
    // Note: If showPartNumber is true and extractedPartNumber is null (e.g., Croma URL),
    // we do nothing here, preserving any manual input from the user.
    
  }, [url, extractedPartNumber, showPartNumber]); // Rerun when URL or derived details change
  // ---------------------------------------------------


  async function formAction(formData) {
    // Manually append the determined storeType
    formData.append('storeType', storeType);
    
    // Manually append the productId/partNumber state value
    if (productId && showPartNumber) {
      formData.append('productId', productId);
    }

    const result = await addProductAction(formData);
    
    if (result?.error) {
      toast.error(result.error);
    } else {
      toast.success("Product added to tracker!");
      formRef.current?.reset();
      setUrl(''); // Clear URL state after successful submission
      setProductId(''); // Clear productId state
    }
  }

  // Determine placeholder based on recognized store
  const placeholderText = storeType === 'unknown' 
    ? "Paste Product URL (e.g., Flipkart, Amazon, Reliance Digital, Vivo, iQOO)"
    : `Paste ${storeType.replace('_', ' ').toUpperCase()} URL`;


  return (
    <form ref={formRef} action={formAction} className="flex flex-col w-full space-y-3">
      <div className="flex w-full items-center space-x-2">
        <Input
          type="text"
          name="url"
          placeholder={placeholderText}
          required
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <Button type="submit">Add Product</Button>
      </div>
      
      {/* Product ID Input Field (Shown for Apple, Croma, Flipkart, Amazon) */}
      {showPartNumber && (
        <Input
          type="text"
          name="productIdManual" // Use a temporary name for the controlled input field
          value={productId} // Value is controlled by React state
          onChange={(e) => setProductId(e.target.value)} // Allows manual input/editing
          placeholder={storeType === 'unicorn' ? "Apple Part Number (e.g., MG6P4HN/A)" : "Product ID (Required for this store)"}
          required={storeType !== 'unicorn'} 
          className="transition-all duration-300"
        />
      )}
      
      {/* Affiliate Link */}
      <Input
        type="text"
        name="affiliateLink"
        placeholder="Your Affiliate Link (Optional)"
      />
    </form>
  );
}