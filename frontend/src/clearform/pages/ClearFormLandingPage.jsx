/**
 * ClearForm Landing Page
 * 
 * Public-facing landing page for ClearForm product.
 */

import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FileText, Zap, CreditCard, Folder, ArrowRight, Check } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { documentsApi, subscriptionsApi } from '../api/clearformApi';

const ClearFormLandingPage = () => {
  const navigate = useNavigate();
  const [documentTypes, setDocumentTypes] = useState([]);
  const [plans, setPlans] = useState([]);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [types, plansData] = await Promise.all([
          documentsApi.getTypes(),
          subscriptionsApi.getPlans(),
        ]);
        setDocumentTypes(types);
        setPlans(plansData);
      } catch (error) {
        console.error('Failed to load data:', error);
      }
    };
    loadData();
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      {/* Header */}
      <header className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <Link to="/clearform" className="flex items-center gap-3">
            <img 
              src="/pleerity-logo.jpg" 
              alt="Pleerity" 
              className="h-8 w-auto"
            />
            <div className="flex flex-col">
              <span className="text-lg font-bold text-slate-900">ClearForm</span>
              <span className="text-xs text-slate-500">by Pleerity</span>
            </div>
          </Link>
          <div className="flex items-center gap-4">
            <Link to="/clearform/login">
              <Button variant="ghost" data-testid="login-btn">Log In</Button>
            </Link>
            <Link to="/clearform/register">
              <Button data-testid="get-started-btn">Get Started Free</Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="container mx-auto px-4 py-20 text-center">
        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-slate-900 max-w-4xl mx-auto leading-tight">
          Professional Documents,{' '}
          <span className="text-emerald-500">Instantly Generated</span>
        </h1>
        <p className="mt-6 text-lg text-slate-600 max-w-2xl mx-auto">
          Tell us what you need in plain English. Our AI creates polished, professional documents in seconds. 
          No templates. No formatting. Just results.
        </p>
        <div className="mt-10 flex flex-col sm:flex-row gap-4 justify-center">
          <Link to="/clearform/register">
            <Button size="lg" className="w-full sm:w-auto gap-2" data-testid="hero-cta">
              Start Creating <ArrowRight className="w-4 h-4" />
            </Button>
          </Link>
          <Button size="lg" variant="outline" className="w-full sm:w-auto" onClick={() => document.getElementById('how-it-works')?.scrollIntoView({ behavior: 'smooth' })}>
            See How It Works
          </Button>
        </div>
        <p className="mt-4 text-sm text-slate-500">5 free credits to get started • No credit card required</p>
      </section>

      {/* Features */}
      <section className="bg-slate-50 py-20">
        <div className="container mx-auto px-4">
          <h2 className="text-3xl font-bold text-center text-slate-900 mb-12">Why ClearForm?</h2>
          <div className="grid md:grid-cols-3 gap-8">
            <Card className="border-0 shadow-lg">
              <CardHeader>
                <div className="w-12 h-12 bg-emerald-100 rounded-lg flex items-center justify-center mb-4">
                  <Zap className="w-6 h-6 text-emerald-600" />
                </div>
                <CardTitle>Intent-Driven</CardTitle>
                <CardDescription>
                  Just describe what you need. Our AI understands context and creates the perfect document.
                </CardDescription>
              </CardHeader>
            </Card>
            <Card className="border-0 shadow-lg">
              <CardHeader>
                <div className="w-12 h-12 bg-emerald-100 rounded-lg flex items-center justify-center mb-4">
                  <CreditCard className="w-6 h-6 text-emerald-600" />
                </div>
                <CardTitle>Pay Per Document</CardTitle>
                <CardDescription>
                  No subscriptions required. Buy credits when you need them, or save with a monthly plan.
                </CardDescription>
              </CardHeader>
            </Card>
            <Card className="border-0 shadow-lg">
              <CardHeader>
                <div className="w-12 h-12 bg-emerald-100 rounded-lg flex items-center justify-center mb-4">
                  <Folder className="w-6 h-6 text-emerald-600" />
                </div>
                <CardTitle>Document Vault</CardTitle>
                <CardDescription>
                  All your generated documents in one place. Access, download, and organize anytime.
                </CardDescription>
              </CardHeader>
            </Card>
          </div>
        </div>
      </section>

      {/* Document Types */}
      <section id="how-it-works" className="py-20">
        <div className="container mx-auto px-4">
          <h2 className="text-3xl font-bold text-center text-slate-900 mb-4">What Can You Create?</h2>
          <p className="text-center text-slate-600 mb-12 max-w-2xl mx-auto">
            Start with these essential document types. More coming soon!
          </p>
          <div className="grid md:grid-cols-3 gap-6 max-w-4xl mx-auto">
            {documentTypes.map((type) => (
              <Card key={type.type} className="hover:shadow-lg transition-shadow">
                <CardHeader>
                  <CardTitle className="text-lg">{type.name}</CardTitle>
                  <CardDescription>{type.description}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-500">
                      {type.credit_cost} credit{type.credit_cost > 1 ? 's' : ''}
                    </span>
                    <span className="text-xs bg-emerald-100 text-emerald-700 px-2 py-1 rounded">
                      Available Now
                    </span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="bg-slate-50 py-20">
        <div className="container mx-auto px-4">
          <h2 className="text-3xl font-bold text-center text-slate-900 mb-4">Simple Pricing</h2>
          <p className="text-center text-slate-600 mb-12">Start free, upgrade when you need more</p>
          <div className="grid md:grid-cols-4 gap-6 max-w-5xl mx-auto">
            {plans.map((plan) => (
              <Card key={plan.plan} className={`relative ${plan.popular ? 'border-emerald-500 border-2' : ''}`}>
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-emerald-500 text-white text-xs px-3 py-1 rounded-full">
                    Most Popular
                  </div>
                )}
                <CardHeader>
                  <CardTitle>{plan.name}</CardTitle>
                  <div className="text-2xl font-bold">{plan.monthly_price_display}</div>
                  <CardDescription>{plan.description}</CardDescription>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2">
                    {plan.features.map((feature, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm">
                        <Check className="w-4 h-4 text-emerald-500 mt-0.5 flex-shrink-0" />
                        <span>{feature}</span>
                      </li>
                    ))}
                  </ul>
                  <Button 
                    className="w-full mt-6" 
                    variant={plan.popular ? 'default' : 'outline'}
                    onClick={() => navigate('/clearform/register')}
                  >
                    {plan.plan === 'free' ? 'Get Started' : 'Choose Plan'}
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20">
        <div className="container mx-auto px-4 text-center">
          <h2 className="text-3xl font-bold text-slate-900 mb-4">Ready to Create Your First Document?</h2>
          <p className="text-slate-600 mb-8">Sign up now and get 5 free credits to try ClearForm.</p>
          <Link to="/clearform/register">
            <Button size="lg" className="gap-2" data-testid="final-cta">
              Get Started Free <ArrowRight className="w-4 h-4" />
            </Button>
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t py-8">
        <div className="container mx-auto px-4 text-center text-sm text-slate-500">
          <p>© 2026 ClearForm by Pleerity Enterprise Ltd. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
};

export default ClearFormLandingPage;
