import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Label } from '../../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Checkbox } from '../../components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Alert, AlertDescription } from '../../components/ui/alert';
import { CheckCircle, AlertCircle, Handshake } from 'lucide-react';

const PartnershipEnquiryForm = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const [form, setForm] = useState({
    first_name: '', last_name: '', role_title: '', work_email: '', phone: '',
    partnership_type: '', partnership_type_other: '',
    company_name: '', country_region: '', website_url: '', organisation_type: '',
    org_description: '', primary_services: '', typical_client_profile: '',
    collaboration_type: '', collaboration_other: '', problem_solved: '',
    works_with_partners: false, org_size: '', gdpr_compliant_status: '', timeline: '',
    additional_notes: '', declaration_accepted: false
  });

  const API_URL = process.env.REACT_APP_BACKEND_URL;

  const partnershipTypes = ['Delivery / Specialist Partner', 'Joint Offering / Co-delivery', 'Referral / Strategic Partner', 'Research / Knowledge Partnership', 'Service Delivery Partnership', 'Technology / Platform Partner', 'Technology integration', 'White label / Reseller', 'Other'];
  const orgTypes = ['Sole trader', 'SME', 'Enterprise', 'Non-profit', 'Public sector', 'University / Research', 'Consultancy / Agency', 'Technology / SaaS', 'Other'];
  const collabTypes = ['Joint delivery of services', 'Integration / tooling alignment', 'Referral arrangement', 'Co-branded offering', 'AI tools design / Implementation', 'Other'];

  const validate = () => {
    if (!form.first_name || !form.last_name || !form.role_title || !form.work_email) return 'Complete all basic fields';
    if (!form.partnership_type) return 'Select partnership type';
    if (!form.company_name || !form.country_region || !form.website_url || !form.organisation_type) return 'Complete organisation details';
    if (!form.org_description || !form.primary_services) return 'Provide organisation description';
    if (!form.collaboration_type || !form.problem_solved) return 'Describe partnership intent';
    if (!form.org_size || !form.gdpr_compliant_status || !form.timeline) return 'Complete readiness section';
    if (!form.declaration_accepted) return 'Accept declaration';
    return null;
  };

  const submit = async (e) => {
    e.preventDefault();
    const err = validate();
    if (err) { setError(err); return; }
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/partnerships/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form)
      });
      if (res.ok) setSuccess(true);
      else setError('Submission failed');
    } catch { setError('Network error'); }
    finally { setLoading(false); }
  };

  if (success) {
    return (
      <PublicLayout>
        <div className="min-h-screen flex items-center justify-center py-20">
          <Card className="max-w-md">
            <CardContent className="pt-6 text-center">
              <CheckCircle className="w-16 h-16 text-green-600 mx-auto mb-4" />
              <h2 className="text-2xl font-bold mb-3">Thank You!</h2>
              <p className="text-gray-600 mb-6">Your partnership enquiry has been received. If suitable, we will contact you.</p>
              <Button onClick={() => navigate('/partnerships')}>Back to Partnerships</Button>
            </CardContent>
          </Card>
        </div>
      </PublicLayout>
    );
  }

  return (
    <PublicLayout>
      <SEOHead title="Partnership Enquiry" canonicalUrl="/partnerships/enquiry" />
      <div className="max-w-4xl mx-auto px-4 py-12">
        <div className="text-center mb-8">
          <Handshake className="w-12 h-12 text-electric-teal mx-auto mb-4" />
          <h1 className="text-3xl font-bold text-midnight-blue mb-2">Partnership Enquiry</h1>
          <p className="text-gray-600">Complete the form below to start a partnership discussion</p>
        </div>

        {error && <Alert variant="destructive" className="mb-6"><AlertCircle className="h-4 w-4" /><AlertDescription>{error}</AlertDescription></Alert>}

        <form onSubmit={submit} className="space-y-8">
          <Card><CardHeader><CardTitle>Basic Identification</CardTitle></CardHeader><CardContent className="space-y-4">
            <div className="grid md:grid-cols-2 gap-4">
              <div><Label>First Name *</Label><Input value={form.first_name} onChange={e => setForm({...form, first_name: e.target.value})} /></div>
              <div><Label>Last Name *</Label><Input value={form.last_name} onChange={e => setForm({...form, last_name: e.target.value})} /></div>
            </div>
            <div><Label>Role / Title *</Label><Input value={form.role_title} onChange={e => setForm({...form, role_title: e.target.value})} /></div>
            <div><Label>Work Email *</Label><Input type="email" value={form.work_email} onChange={e => setForm({...form, work_email: e.target.value})} /></div>
            <div><Label>Phone</Label><Input value={form.phone} onChange={e => setForm({...form, phone: e.target.value})} /></div>
          </CardContent></Card>

          <Card><CardHeader><CardTitle>Partnership Type</CardTitle></CardHeader><CardContent className="space-y-4">
            <div>
              <Label>Partnership Type *</Label>
              <Select value={form.partnership_type} onValueChange={v => setForm({...form, partnership_type: v})}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{partnershipTypes.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            {form.partnership_type === 'Other' && <div><Label>Please specify</Label><Input value={form.partnership_type_other} onChange={e => setForm({...form, partnership_type_other: e.target.value})} /></div>}
          </CardContent></Card>

          <Card><CardHeader><CardTitle>About Your Organisation</CardTitle></CardHeader><CardContent className="space-y-4">
            <div><Label>Company Name *</Label><Input value={form.company_name} onChange={e => setForm({...form, company_name: e.target.value})} /></div>
            <div className="grid md:grid-cols-2 gap-4">
              <div><Label>Country / Region *</Label><Input value={form.country_region} onChange={e => setForm({...form, country_region: e.target.value})} /></div>
              <div><Label>Website URL *</Label><Input value={form.website_url} onChange={e => setForm({...form, website_url: e.target.value})} /></div>
            </div>
            <div>
              <Label>Organisation Type *</Label>
              <Select value={form.organisation_type} onValueChange={v => setForm({...form, organisation_type: v})}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{orgTypes.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label>Brief description *</Label><Textarea value={form.org_description} onChange={e => setForm({...form, org_description: e.target.value})} className="min-h-[100px]" /></div>
            <div><Label>Primary services *</Label><Textarea value={form.primary_services} onChange={e => setForm({...form, primary_services: e.target.value})} /></div>
            <div><Label>Typical client profile</Label><Textarea value={form.typical_client_profile} onChange={e => setForm({...form, typical_client_profile: e.target.value})} /></div>
          </CardContent></Card>

          <Card><CardHeader><CardTitle>Partnership Intent</CardTitle></CardHeader><CardContent className="space-y-4">
            <div>
              <Label>Collaboration type *</Label>
              <Select value={form.collaboration_type} onValueChange={v => setForm({...form, collaboration_type: v})}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{collabTypes.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label>What problem does this solve? *</Label><Textarea value={form.problem_solved} onChange={e => setForm({...form, problem_solved: e.target.value})} className="min-h-[100px]" /></div>
          </CardContent></Card>

          <Card><CardHeader><CardTitle>Readiness & Scale</CardTitle></CardHeader><CardContent className="space-y-4">
            <div className="flex items-center space-x-2">
              <Checkbox checked={form.works_with_partners} onCheckedChange={c => setForm({...form, works_with_partners: c})} />
              <label className="text-sm">We currently work with other partners</label>
            </div>
            <div>
              <Label>Organisation size *</Label>
              <Select value={form.org_size} onValueChange={v => setForm({...form, org_size: v})}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="Solo">Solo</SelectItem>
                  <SelectItem value="2-10">2-10</SelectItem>
                  <SelectItem value="11-50">11-50</SelectItem>
                  <SelectItem value="50+">50+</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>GDPR compliant? *</Label>
              <Select value={form.gdpr_compliant_status} onValueChange={v => setForm({...form, gdpr_compliant_status: v})}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="Yes">Yes</SelectItem>
                  <SelectItem value="In progress">In progress</SelectItem>
                  <SelectItem value="Not yet">Not yet</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Timeline *</Label>
              <Select value={form.timeline} onValueChange={v => setForm({...form, timeline: v})}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="Immediate">Immediate</SelectItem>
                  <SelectItem value="3-6 months">3-6 months</SelectItem>
                  <SelectItem value="Exploratory">Exploratory</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div><Label>Additional notes</Label><Textarea value={form.additional_notes} onChange={e => setForm({...form, additional_notes: e.target.value})} /></div>
          </CardContent></Card>

          <Card><CardContent className="pt-6">
            <div className="flex items-start space-x-2">
              <Checkbox checked={form.declaration_accepted} onCheckedChange={c => setForm({...form, declaration_accepted: c})} />
              <label className="text-sm">I understand that submission does not guarantee a partnership and that Pleerity Enterprise Ltd reviews proposals based on strategic alignment and capacity. *</label>
            </div>
            <Button type="submit" disabled={loading} className="w-full mt-6 bg-electric-teal hover:bg-electric-teal/90">
              {loading ? 'Submitting...' : 'Submit Partnership Enquiry'}
            </Button>
          </CardContent></Card>
        </form>
      </div>
    </PublicLayout>
  );
};

export default PartnershipEnquiryForm;
