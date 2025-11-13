'use client';

import { useRef, useState, useEffect } from 'react'; // Added useEffect
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

/**
 * Extracts the Apple Part Number from an Apple product URL.
 * Example URL segment: /product/MG6P4HN/A/some-name
 * @param {string} url 
 * @returns {string | null} The part number or null if not found.
 */
function extractApplePartNumber(url) {
  // Regex to find a pattern like /product/PART_NUMBER/
  const match = url.match(/\/product\/([A-Z0-9\/]+)\//i);
  if (match && match[1]) {
    // The part number is the first captured group (e.g., MG6P4HN/A)
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
    // Pass the extracted part number back
    return { storeType: 'unicorn', showPartNumber: true, extractedPartNumber: partNumber };
  }
  if (lowerUrl.includes('reliancedigital.in')) {
    return { storeType: 'reliance_digital', showPartNumber: false, extractedPartNumber: null };
  }
  // ... other stores ...
  if (lowerUrl.includes('croma.com') || lowerUrl.includes('flipkart.com') || lowerUrl.includes('amazon.in')) {
    // Show the product ID field for manual entry (no automatic extraction here)
    return { storeType: 'unknown', showPartNumber: true, extractedPartNumber: null }; 
  }

  // Default fallback or general case
  return { storeType: 'unknown', showPartNumber: false, extractedPartNumber: null };
}


export function AddProductForm({ addProductAction }) {
  const formRef = useRef(null);
  const [url, setUrl] = useState('');
  // New state to hold the product ID/part number, which can be extracted or manually entered
  const [productId, setProductId] = useState(''); 
  
  // Use the new derived details
  const { storeType, showPartNumber, extractedPartNumber } = getStoreDetails(url);

  // --- NEW useEffect hook to handle auto-population ---
  useEffect(() => {
    // If a part number was extracted from the URL, set it as the default productId
    if (extractedPartNumber) {
      setProductId(extractedPartNumber);
    } else if (storeType !== 'unicorn' && showPartNumber) {
      // If the field is shown but it's not an Apple store, clear the productId 
      // state since extraction is only for Apple right now, requiring manual entry for others.
      setProductId('');
    } else if (!showPartNumber) {
        // Clear if the input field is hidden entirely
        setProductId('');
    }
  }, [url, extractedPartNumber, storeType, showPartNumber]); // Rerun when URL or derived details change
  // ---------------------------------------------------


  async function formAction(formData) {
    // Manually append the determined storeType
    formData.append('storeType', storeType);
    
    // Manually append the productId/partNumber state value since we control its value now
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
      
      {showPartNumber && (
        <Input
          type="text"
          name="productIdManual" // Use a different name for the controlled input field to avoid conflict
          // Use the state value and update the state on change
          value={productId} 
          onChange={(e) => setProductId(e.target.value)}
          placeholder={storeType === 'unicorn' ? "Apple Part Number (e.g., MG6P4HN/A)" : "Product ID (Required for this store)"}
          // The required prop is now handled by checking the state value in formAction 
          required={storeType !== 'unicorn'} 
          className="transition-all duration-300"
        />
      )}
      
      {/* Remove the hidden storeType input as it's appended in formAction */}
      
      {/* Affiliate Link */}
      <Input
        type="text"
        name="affiliateLink"
        placeholder="Your Affiliate Link (Optional)"
      />
    </form>
  );
}