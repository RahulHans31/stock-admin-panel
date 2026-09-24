import { prisma } from '@/lib/prisma';
import { addProduct, deleteProduct, updateTargetPrice } from '@/app/actions';

// Import our new shadcn components
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { AddProductForm } from './components/AddProductForm';
import { DeleteProductButton } from './components/DeleteProductButton';
import { SetTargetPriceButton } from './components/SetTargetPriceButton';

/**
 * This is the main page component.
 */
export default async function Home() {
  // 1. Fetch all products
  const products = await prisma.product.findMany({
    orderBy: { createdAt: 'desc' },
  });

  return (
    <main className="min-h-screen bg-gradient-to-br from-background via-background to-muted/20">
      <div className="max-w-5xl mx-auto p-4 md:p-8 py-8 md:py-12">
        <div className="mb-8 md:mb-12">
          <h1 className="text-4xl md:text-5xl font-bold mb-2 bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
            Stock Tracker Admin
          </h1>
          <p className="text-muted-foreground text-sm md:text-base">
            Monitor and manage product availability across multiple stores
          </p>
        </div>

        <Card className="mb-6 border-2 hover:border-primary/20 transition-colors">
          <CardHeader>
            <CardTitle className="text-xl">Add New Product</CardTitle>
            <CardDescription>
              Paste a product URL from supported stores to start tracking
            </CardDescription>
          </CardHeader>
          <CardContent>
            <AddProductForm addProductAction={addProduct} />
          </CardContent>
        </Card>

        <Card className="border-2">
          <CardHeader className="border-b">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <div>
                <CardTitle className="text-xl">Tracked Products</CardTitle>
                <CardDescription className="mt-1">
                  {products.length === 0
                    ? 'No products tracked yet'
                    : `${products.length} product${products.length === 1 ? '' : 's'} being monitored`
                  }
                </CardDescription>
              </div>
              {products.length > 0 && (
                <div className="flex items-center gap-2 text-xs text-muted-foreground bg-muted/50 px-3 py-1.5 rounded-md">
                  <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                  Active
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent border-b">
                    <TableHead className="font-semibold">Product</TableHead>
                    <TableHead className="font-semibold hidden sm:table-cell">Store</TableHead>
                    <TableHead className="font-semibold hidden md:table-cell">Target Price</TableHead>
                    <TableHead className="text-right font-semibold">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {products.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={4} className="h-32 text-center">
                        <div className="flex flex-col items-center justify-center text-muted-foreground">
                          <svg className="w-12 h-12 mb-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                          </svg>
                          <p className="font-medium">No products yet</p>
                          <p className="text-sm">Add your first product above to get started</p>
                        </div>
                      </TableCell>
                    </TableRow>
                  ) : (
                    products.map((product, index) => (
                      <TableRow
                        key={product.id}
                        className="group hover:bg-muted/50 transition-colors"
                      >
                        <TableCell className="font-medium py-4">
                          <div className="flex flex-col gap-1">
                            <span className="line-clamp-2">{product.name}</span>
                            <span className="sm:hidden text-xs text-muted-foreground capitalize">
                              {product.storeType.replace('_', ' ')}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="hidden sm:table-cell">
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-primary/10 text-primary border border-primary/20">
                            <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                            {product.storeType.replace('_', ' ')}
                          </span>
                        </TableCell>
                        <TableCell className="hidden md:table-cell py-4">
                          {product.storeType === 'flipkart' ? (
                            <SetTargetPriceButton
                              id={product.id}
                              currentTargetPrice={product.targetPrice != null ? Number(product.targetPrice) : null}
                              updateTargetPriceAction={updateTargetPrice}
                            />
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </TableCell>
                        <TableCell className="text-right py-4">
                          <DeleteProductButton
                            id={product.id}
                            deleteProductAction={deleteProduct}
                          />
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}