'use server';

import { prisma } from '@/lib/prisma';
import { revalidatePath } from 'next/cache';

// This function parses the URL you paste in
function getProductDetails(url, partNumber) {
  try {
    const parsedUrl = new URL(url);

    // --- NEW FLIPKART LOGIC ---
    if (parsedUrl.hostname.includes('flipkart.com')) {
      // Flipkart ID is in the 'pid' query parameter
      const pid = parsedUrl.searchParams.get('pid');
      if (!pid) {
        throw new Error('Flipkart URL is missing a "pid" query parameter.');
      }
      // Get a name from the URL path
      const name = (parsedUrl.pathname.split('/')[1] || 'Flipkart Product')
                   .replace(/-/g, ' ').slice(0, 50) + '...';
      return {
        name: `(Flipkart) ${name}`,
        productId: pid, // For Flipkart, the PID is the Product ID
        storeType: 'flipkart',
        partNumber: null
      };
    }

    // --- AMAZON LOGIC ---
    if (parsedUrl.hostname.includes('amazon.in')) {
      // Find the ASIN, which is usually after /dp/
      const pathParts = parsedUrl.pathname.split('/');
      const dpIndex = pathParts.indexOf('dp');
      
      if (dpIndex === -1 || !pathParts[dpIndex + 1]) {
        throw new Error('Could not find a valid ASIN (e.g., /dp/B0CX59H5W7) in the Amazon URL.');
      }
      
      const asin = pathParts[dpIndex + 1];
      const name = (pathParts[dpIndex - 1] || 'Amazon Product')
                   .replace(/-/g, ' ').slice(0, 50) + '...';
      
      return {
        name: `(Amazon) ${name}`,
        productId: asin, // For Amazon, the ASIN is the Product ID
        storeType: 'amazon',
        partNumber: null // We don't need this for Amazon
      };
    }

    // --- APPLE LOGIC ---
    if (parsedUrl.hostname.includes('apple.com')) {
      if (!partNumber) {
        throw new Error('Apple products require a Part Number.');
      }
      const name = (parsedUrl.pathname.split('/')[3] || 'Apple Product')
                   .replace(/-/g, ' ').slice(0, 50) + '...';
      return {
        name: `(Apple) ${name}`,
        productId: partNumber,
        storeType: 'apple',
        partNumber: partNumber
      };
    }
    
    // --- CROMA LOGIC ---
    if (parsedUrl.hostname.includes('croma.com')) {
      const pathParts = parsedUrl.pathname.split('/');
      const pid = pathParts[pathParts.length - 1];
      if (!pid || !/^\d+$/.test(pid)) throw new Error('Could not find a valid product ID in the Croma URL.');
      const name = (pathParts[1] || 'Croma Product')
                   .replace(/-/g, ' ').slice(0, 50) + '...';
      return { 
        name: `(Croma) ${name}`, 
        productId: pid, 
        storeType: 'croma', 
        partNumber: null 
      };
    }
    
    // --- IQOO LOGIC ---
    if (parsedUrl.hostname.includes('iqoo.com')) {
      // The product ID is the last path segment (ID after /product/)
      const pathParts = parsedUrl.pathname.split('/').filter(part => part.length > 0);
      const productSlug = pathParts[pathParts.length - 1]; 
      
      if (!productSlug) {
        throw new Error('Could not find a product slug in the iQOO URL.');
      }
      
      // Use the product slug as the identifier for the DB and a name in the list
      return {
        name: `(iQOO) ${productSlug}`, 
        productId: productSlug, 
        storeType: 'iqoo',
        partNumber: null
      };
    }

    // --- VIVO LOGIC ---
    if (parsedUrl.hostname.includes('vivo.com')) {
      // Vivo product ID is typically the number after /product/
      const pathParts = parsedUrl.pathname.split('/').filter(part => part.length > 0);
      const productIndex = pathParts.indexOf('product');
      
      if (productIndex === -1 || !pathParts[productIndex + 1]) {
        throw new Error('Could not find a product ID in the Vivo URL after /product/.');
      }
      
      const productId = pathParts[productIndex + 1].split('?')[0]; // Remove query params like skuId
      const name = `Vivo Product ID ${productId}`;
      
      return {
        name: name, 
        productId: productId, 
        storeType: 'vivo',
        partNumber: null
      };
    }


    // --- UPDATED ERROR MESSAGE ---
    throw new Error('Sorry, only Croma, Apple, Amazon, Flipkart, iQOO, and Vivo URLs are supported.');
  
  } catch (error) {
    return { error: error.message };
  }
}

// Server Action to add a product (no changes needed)
export async function addProduct(formData) {
  const url = formData.get('url');
  const partNumber = formData.get('partNumber');
  const affiliateLink = formData.get('affiliateLink');

  if (!url) return { error: 'URL is required.' };

  const details = getProductDetails(url, partNumber);
  if (details.error) return { error: details.error };

  try {
    await prisma.product.create({
      data: {
        name: details.name,
        url: url,
        productId: details.productId,
        storeType: details.storeType,
        partNumber: details.partNumber,
        affiliateLink: affiliateLink || null,
      },
    });
    revalidatePath('/');
    return { success: `Added ${details.name}` };
  } catch (error) {
    console.error(error);
    return { error: 'Failed to add product. Is it a duplicate?' };
  }
}

// deleteProduct (no changes needed)
export async function deleteProduct(id) {
  if (!id) return;
  try {
    await prisma.product.delete({ where: { id: id } });
    revalidatePath('/');
  } catch (error) {}
}