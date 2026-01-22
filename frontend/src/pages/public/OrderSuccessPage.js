import React, { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import {
  CheckCircle2,
  Clock,
  Mail,
  FileText,
  ArrowRight,
  Loader2,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const OrderSuccessPage = () => {
  const [searchParams] = useSearchParams();
  const orderId = searchParams.get('order_id');
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    const fetchOrder = async () => {
      if (!orderId) {
        setLoading(false);
        return;
      }
      
      try {
        const response = await fetch(`${API_URL}/api/orders/${orderId}/status`);
        if (response.ok) {
          const data = await response.json();
          setOrder(data);
        }
      } catch (err) {
        console.error('Failed to fetch order:', err);
      } finally {
        setLoading(false);
      }
    };
    
    fetchOrder();
  }, [orderId]);
  
  return (
    <PublicLayout>
      <SEOHead
        title="Order Confirmed - Pleerity Enterprise"
        description="Your order has been successfully placed."
      />
      
      <div className="min-h-screen bg-gray-50 py-20">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8">
          <Card className="border-0 shadow-xl">
            <CardHeader className="text-center pb-2">
              <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <CheckCircle2 className="w-10 h-10 text-green-600" />
              </div>
              <CardTitle className="text-3xl text-midnight-blue">Order Confirmed!</CardTitle>
              <CardDescription className="text-lg">
                Thank you for your order. We&apos;re on it!
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {loading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="h-8 w-8 animate-spin text-electric-teal" />
                </div>
              ) : (
                <>
                  {/* Order Reference */}
                  {orderId && (
                    <div className="bg-gray-50 rounded-lg p-4 text-center">
                      <p className="text-sm text-gray-500 mb-1">Order Reference</p>
                      <p className="text-2xl font-mono font-bold text-midnight-blue">{orderId}</p>
                    </div>
                  )}
                  
                  {/* What Happens Next */}
                  <div className="space-y-4">
                    <h3 className="font-semibold text-midnight-blue">What happens next?</h3>
                    
                    <div className="flex items-start gap-4">
                      <div className="w-10 h-10 bg-electric-teal/10 rounded-lg flex items-center justify-center shrink-0">
                        <Mail className="w-5 h-5 text-electric-teal" />
                      </div>
                      <div>
                        <p className="font-medium">Confirmation Email</p>
                        <p className="text-sm text-gray-600">
                          You&apos;ll receive an email confirmation with your order details shortly.
                        </p>
                      </div>
                    </div>
                    
                    <div className="flex items-start gap-4">
                      <div className="w-10 h-10 bg-electric-teal/10 rounded-lg flex items-center justify-center shrink-0">
                        <FileText className="w-5 h-5 text-electric-teal" />
                      </div>
                      <div>
                        <p className="font-medium">Document Preparation</p>
                        <p className="text-sm text-gray-600">
                          Our team will begin preparing your documents. We may contact you if we need any additional information.
                        </p>
                      </div>
                    </div>
                    
                    <div className="flex items-start gap-4">
                      <div className="w-10 h-10 bg-electric-teal/10 rounded-lg flex items-center justify-center shrink-0">
                        <Clock className="w-5 h-5 text-electric-teal" />
                      </div>
                      <div>
                        <p className="font-medium">Delivery</p>
                        <p className="text-sm text-gray-600">
                          Your completed documents will be delivered within the specified timeframe, typically 24-48 hours.
                        </p>
                      </div>
                    </div>
                  </div>
                  
                  {/* Order Details if available */}
                  {order && (
                    <div className="border-t pt-4">
                      <h4 className="font-medium mb-2">Order Details</h4>
                      <div className="grid grid-cols-2 gap-2 text-sm">
                        <div><span className="text-gray-500">Service:</span></div>
                        <div>{order.service_name}</div>
                        <div><span className="text-gray-500">Status:</span></div>
                        <div className="capitalize">{order.status?.replace(/_/g, ' ').toLowerCase()}</div>
                        {order.pricing?.total_amount && (
                          <>
                            <div><span className="text-gray-500">Total Paid:</span></div>
                            <div>£{(order.pricing.total_amount / 100).toFixed(2)}</div>
                          </>
                        )}
                      </div>
                    </div>
                  )}
                  
                  {/* Actions */}
                  <div className="flex flex-col sm:flex-row gap-4 pt-4">
                    <Button
                      className="flex-1 bg-electric-teal hover:bg-electric-teal/90"
                      asChild
                    >
                      <Link to="/services/catalogue">
                        Browse More Services
                        <ArrowRight className="w-4 h-4 ml-2" />
                      </Link>
                    </Button>
                    <Button variant="outline" className="flex-1" asChild>
                      <Link to="/contact">
                        Contact Support
                      </Link>
                    </Button>
                  </div>
                  
                  {/* Support Info */}
                  <p className="text-center text-sm text-gray-500 pt-4">
                    Questions about your order? Email us at{' '}
                    <a href="mailto:support@pleerity.com" className="text-electric-teal hover:underline">
                      support@pleerity.com
                    </a>
                  </p>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </PublicLayout>
  );
};

export default OrderSuccessPage;
