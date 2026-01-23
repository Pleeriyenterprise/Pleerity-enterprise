import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '../../components/ui/tabs';
import {
  Search,
  ArrowRight,
  FileText,
  Clock,
  Shield,
  Building2,
  Sparkles,
  ClipboardCheck,
  Package,
  Loader2,
  AlertCircle,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Category icons
const categoryIcons = {
  CVP_FEATURE: Shield,
  CVP_ADDON: ClipboardCheck,
  STANDALONE_REPORT: Sparkles,
  DOCUMENT_PACK: FileText,
};

// Category colors
const categoryColors = {
  CVP_FEATURE: 'bg-blue-500',
  CVP_ADDON: 'bg-amber-500',
  STANDALONE_REPORT: 'bg-purple-500',
  DOCUMENT_PACK: 'bg-green-500',
};

// Category labels
const categoryLabels = {
  CVP_FEATURE: 'CVP Features',
  CVP_ADDON: 'CVP Add-ons',
  STANDALONE_REPORT: 'Standalone Reports',
  DOCUMENT_PACK: 'Document Packs',
};

const ServicesCataloguePage = () => {
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [sortBy, setSortBy] = useState('name');
  
  // Fetch services from API
  useEffect(() => {
    const fetchServices = async () => {
      try {
        setLoading(true);
        const response = await fetch(`${API_URL}/api/public/services`);
        
        if (!response.ok) {
          throw new Error('Failed to load services');
        }
        
        const data = await response.json();
        setServices(data.services || []);
        
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    
    fetchServices();
  }, []);
  
  // Format price
  const formatPrice = (pence) => {
    if (!pence || pence === 0) return 'Included';
    return `£${(pence / 100).toFixed(2)}`;
  };
  
  // Filter and sort services
  const filteredServices = services
    .filter(service => {
      // Search filter
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        return (
          service.service_name.toLowerCase().includes(query) ||
          service.description?.toLowerCase().includes(query) ||
          service.service_code.toLowerCase().includes(query)
        );
      }
      return true;
    })
    .filter(service => {
      // Category filter
      if (selectedCategory === 'all') return true;
      return service.category === selectedCategory;
    })
    .sort((a, b) => {
      // Sort
      switch (sortBy) {
        case 'price-low':
          return (a.price_amount || 0) - (b.price_amount || 0);
        case 'price-high':
          return (b.price_amount || 0) - (a.price_amount || 0);
        case 'name':
        default:
          return a.service_name.localeCompare(b.service_name);
      }
    });
  
  // Group services by category
  const servicesByCategory = {
    STANDALONE_REPORT: filteredServices.filter(s => s.category === 'STANDALONE_REPORT'),
    DOCUMENT_PACK: filteredServices.filter(s => s.category === 'DOCUMENT_PACK'),
    CVP_ADDON: filteredServices.filter(s => s.category === 'CVP_ADDON'),
    CVP_FEATURE: filteredServices.filter(s => s.category === 'CVP_FEATURE'),
  };
  
  // Render service card
  const renderServiceCard = (service) => {
    const Icon = categoryIcons[service.category] || Package;
    const colorClass = categoryColors[service.category] || 'bg-gray-500';
    const canOrder = service.pricing_model !== 'included' && service.price_amount > 0;
    
    return (
      <Card 
        key={service.service_code} 
        className="h-full border-0 shadow-lg hover:shadow-xl transition-all hover:-translate-y-1 group"
        data-testid={`service-card-${service.service_code}`}
      >
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between">
            <div className={`w-12 h-12 ${colorClass} rounded-xl flex items-center justify-center`}>
              <Icon className="w-6 h-6 text-white" />
            </div>
            <Badge variant="outline" className="text-xs">
              {categoryLabels[service.category]}
            </Badge>
          </div>
          <CardTitle className="text-lg mt-3">{service.service_name}</CardTitle>
          <CardDescription className="line-clamp-2">
            {service.description}
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-0">
          {/* Features */}
          <div className="flex items-center gap-3 text-xs text-gray-500 mb-4">
            {service.documents_generated && service.documents_generated.length > 0 && (
              <div className="flex items-center gap-1">
                <FileText className="h-3 w-3" />
                <span>{service.documents_generated.length} docs</span>
              </div>
            )}
            {service.turnaround_hours && (
              <div className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                <span>{service.turnaround_hours}h</span>
              </div>
            )}
            {service.review_required && (
              <div className="flex items-center gap-1">
                <Shield className="h-3 w-3" />
                <span>Reviewed</span>
              </div>
            )}
          </div>
          
          {/* Price & CTA */}
          <div className="flex items-center justify-between pt-4 border-t">
            <div>
              <p className="text-xl font-bold text-midnight-blue">
                {formatPrice(service.price_amount)}
              </p>
              {service.price_amount > 0 && (
                <p className="text-xs text-gray-500">+ VAT</p>
              )}
            </div>
            {canOrder ? (
              <Button
                asChild
                className="bg-electric-teal hover:bg-electric-teal/90 group-hover:translate-x-1 transition-transform"
                data-testid={`btn-order-${service.service_code}`}
              >
                <Link to={`/order/intake?service=${service.service_code}`}>
                  Order Now
                  <ArrowRight className="w-4 h-4 ml-1" />
                </Link>
              </Button>
            ) : service.requires_cvp_subscription ? (
              <Button variant="outline" asChild>
                <Link to="/compliance-vault-pro">
                  Get CVP
                  <ArrowRight className="w-4 h-4 ml-1" />
                </Link>
              </Button>
            ) : (
              <Badge variant="secondary">Included in CVP</Badge>
            )}
          </div>
        </CardContent>
      </Card>
    );
  };
  
  if (loading) {
    return (
      <PublicLayout>
        <div className="min-h-screen flex items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-electric-teal" />
        </div>
      </PublicLayout>
    );
  }
  
  if (error) {
    return (
      <PublicLayout>
        <section className="py-32 text-center">
          <AlertCircle className="h-16 w-16 text-red-500 mx-auto mb-4" />
          <h1 className="text-3xl font-bold text-midnight-blue mb-4">Unable to Load Services</h1>
          <p className="text-gray-600 mb-8">{error}</p>
          <Button onClick={() => window.location.reload()}>Try Again</Button>
        </section>
      </PublicLayout>
    );
  }
  
  return (
    <PublicLayout>
      <SEOHead
        title="Service Catalogue - Professional Property Services"
        description="Browse our complete catalogue of property services including market research, document packs, compliance audits, and AI-powered reports."
        canonicalUrl="/services/catalogue"
      />
      
      {/* Hero Section */}
      <section className="py-16 bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto">
            <h1 className="text-4xl sm:text-5xl font-bold text-midnight-blue mb-6">
              Service Catalogue
            </h1>
            <p className="text-xl text-gray-600 mb-8">
              Professional property services designed for landlords, investors, and property managers.
              Order online and receive your documents within 48 hours.
            </p>
            
            {/* Search & Filter */}
            <div className="flex flex-col sm:flex-row gap-4 max-w-2xl mx-auto">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Search services..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                  data-testid="search-services"
                />
              </div>
              <Select value={selectedCategory} onValueChange={setSelectedCategory}>
                <SelectTrigger className="w-full sm:w-48" data-testid="filter-category">
                  <SelectValue placeholder="Category" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Categories</SelectItem>
                  <SelectItem value="STANDALONE_REPORT">Standalone Reports</SelectItem>
                  <SelectItem value="DOCUMENT_PACK">Document Packs</SelectItem>
                  <SelectItem value="CVP_ADDON">CVP Add-ons</SelectItem>
                  <SelectItem value="CVP_FEATURE">CVP Features</SelectItem>
                </SelectContent>
              </Select>
              <Select value={sortBy} onValueChange={setSortBy}>
                <SelectTrigger className="w-full sm:w-40" data-testid="sort-services">
                  <SelectValue placeholder="Sort by" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="name">Name (A-Z)</SelectItem>
                  <SelectItem value="price-low">Price (Low to High)</SelectItem>
                  <SelectItem value="price-high">Price (High to Low)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>
      </section>
      
      {/* Services Grid */}
      <section className="py-12 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {filteredServices.length === 0 ? (
            <div className="text-center py-16">
              <Package className="h-16 w-16 text-gray-300 mx-auto mb-4" />
              <h3 className="text-xl font-medium text-gray-600 mb-2">No services found</h3>
              <p className="text-gray-500">Try adjusting your search or filters</p>
            </div>
          ) : selectedCategory === 'all' ? (
            // Show by category
            <Tabs defaultValue="reports" className="w-full">
              <TabsList className="grid w-full grid-cols-4 mb-8">
                <TabsTrigger value="reports" className="text-xs sm:text-sm">
                  Reports ({servicesByCategory.STANDALONE_REPORT.length})
                </TabsTrigger>
                <TabsTrigger value="documents" className="text-xs sm:text-sm">
                  Documents ({servicesByCategory.DOCUMENT_PACK.length})
                </TabsTrigger>
                <TabsTrigger value="addons" className="text-xs sm:text-sm">
                  Add-ons ({servicesByCategory.CVP_ADDON.length})
                </TabsTrigger>
                <TabsTrigger value="cvp" className="text-xs sm:text-sm">
                  CVP ({servicesByCategory.CVP_FEATURE.length})
                </TabsTrigger>
              </TabsList>
              
              <TabsContent value="reports">
                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {servicesByCategory.STANDALONE_REPORT.map(renderServiceCard)}
                </div>
              </TabsContent>
              
              <TabsContent value="documents">
                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {servicesByCategory.DOCUMENT_PACK.map(renderServiceCard)}
                </div>
              </TabsContent>
              
              <TabsContent value="addons">
                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {servicesByCategory.CVP_ADDON.map(renderServiceCard)}
                </div>
              </TabsContent>
              
              <TabsContent value="cvp">
                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {servicesByCategory.CVP_FEATURE.map(renderServiceCard)}
                </div>
              </TabsContent>
            </Tabs>
          ) : (
            // Show filtered results
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredServices.map(renderServiceCard)}
            </div>
          )}
          
          {/* Results count */}
          <p className="text-center text-gray-500 mt-8">
            Showing {filteredServices.length} of {services.length} services
          </p>
        </div>
      </section>
      
      {/* CTA Section */}
      <section className="py-16 bg-midnight-blue">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">
            Need a Custom Solution?
          </h2>
          <p className="text-lg text-gray-300 mb-8">
            Can&apos;t find exactly what you need? Our team can create bespoke reports and document packs tailored to your requirements.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button
              size="lg"
              className="bg-electric-teal hover:bg-electric-teal/90 text-white"
              asChild
            >
              <Link to="/contact">Contact Us</Link>
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="border-white text-white hover:bg-white hover:text-midnight-blue"
              asChild
            >
              <Link to="/booking">Book a Consultation</Link>
            </Button>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
};

export default ServicesCataloguePage;
