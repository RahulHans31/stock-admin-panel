'use server';

import * as cheerio from 'cheerio';
import { prisma } from '@/lib/prisma';
import { revalidatePath } from 'next/cache';

/**
 * Fetches the Reliance Digital product page and scrapes the internal Article ID (Item Code).
 * This replaces the need for the Python scraper in this case.
 * @param {string} url - The full Reliance Digital product URL.
 * @returns {Promise<string|null>} The internal 9-digit Article ID string or null.
 */
async function getRelianceDigitalArticleId(url) {
    try {
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                // Using a mobile-like user agent to ensure correct page structure is received
                'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36',
            },
        });

        if (!response.ok) {
            console.error(`[RD Scraper] HTTP error fetching ${url}: ${response.status}`);
            return null;
        }

        const html = await response.text();
        const $ = cheerio.load(html);

        let articleId = null;

        // 1. Target the <li> in the specifications section that lists "Item Code"
        $('li.specifications-list').each((i, el) => {
            const label = $(el).find('span:first-child').text().trim();
            if (label === 'Item Code') {
                // The value is nested inside the span with class 'specifications-list--right' and then within a <ul>
                articleId = $(el).find('.specifications-list--right ul').text().trim();
                return false; // Stop the loop once the ID is found
            }
        });

        // 2. Fallback: Check the og:image URL in metadata (less reliable but often present)
        if (!articleId) {
            const imageMeta = $('meta[property="og:image"]').attr('content');
            if (imageMeta) {
                // Use regex to find the 9-digit number right before '-i-1' in the filename
                const match = imageMeta.match(/-(\d{9})-i-1/);
                if (match) {
                    articleId = match[1];
                }
            }
        }

        return articleId;
    } catch (error) {
        console.error("[RD Scraper] Scraping failed:", error.message);
        return null;
    }
}


// This function parses the URL you paste in
async function getProductDetails(url, partNumber) {
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
    if (parsedUrl.hostname.includes('reliancedigital.in')) {
            // 1. SCALING ACTION: Scrape the actual internal Article ID
            const internalArticleId = await getRelianceDigitalArticleId(url);
            
            if (!internalArticleId) {
                throw new Error('Could not extract the internal Item Code from the Reliance Digital page.');
            }

            // 2. Extract slug and name for database
            const pathParts = parsedUrl.pathname.split('/').filter(p => p.length > 0);
            const slug = pathParts[pathParts.length - 1]; 
            const nameBase = pathParts.length > 1 ? pathParts[pathParts.length - 2] : slug;
            const name = nameBase.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase()).slice(0, 50) + '...';

            return { 
                name: `(R. Digital) ${name}`, 
                // Store the actual scraped internal Article ID for API tracking
                productId: internalArticleId, 
                storeType: 'reliance_digital', 
                partNumber: slug 
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