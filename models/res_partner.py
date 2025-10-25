import math
from odoo import api, models, fields

class ResPartner(models.Model):
    """
        DOCSTRING: ResPartner model inherits from res.partner and adds a new field called loan_account to the partner.
    """
    _inherit = 'res.partner'

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

    @api.depends('loan_ids.loan_repayment_ids.status', 'loan_ids.loan_repayment_ids.remaining_balance')
    def _compute_loan_remaining_total(self):
        for partner in self:
            total = 0.0
            for loan in partner.loan_ids:
                if loan.loan_status == 'disbursed':
                    for rep in loan.loan_repayment_ids:
                        if rep.status in ['pending', 'extra']:
                            total += rep.principal
            partner.loan_remaining_total = total