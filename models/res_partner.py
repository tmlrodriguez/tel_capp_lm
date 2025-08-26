import math
from odoo import api, models, fields

class ResPartner(models.Model):
    """
        DOCSTRING: ResPartner model inherits from res.partner and adds a new field called loan_account to the partner.
    """
    _inherit = 'res.partner'

    loan_account = fields.Many2one(
        'account.account',
        string='Cuenta de Préstamos',
        company_dependent=True,
        domain="[('code', '=ilike', '1%')]"
    )

    loan_ids = fields.One2many(
        'loan.manager.loan',
        'partner_id',
        string='Préstamos',
    )

    loan_remaining_total = fields.Float(
        string='Saldo Pendiente Total',
        compute='_compute_loan_remaining_total',
        readonly=True
    )

    @api.onchange('company_id')
    def _onchange_company_id(self):
        active_company_id = self.company_id.id or self.env.company.id
        return {
            'domain': {
                'loan_account': [('company_ids', 'in', [active_company_id])]
            }
        }

    @api.depends('loan_ids.loan_repayment_ids.status', 'loan_ids.loan_repayment_ids.remaining_balance')
    def _compute_loan_remaining_total(self):
        for partner in self:
            total = 0.0
            for loan in partner.loan_ids:
                if loan.loan_status == 'disbursed':
                    for rep in loan.loan_repayment_ids:
                        if rep.status == 'pending':
                            total += rep.principal
            partner.loan_remaining_total = math.floor(total)