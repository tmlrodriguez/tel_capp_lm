from odoo import models, fields, api
from odoo.exceptions import ValidationError

# Define your models here.


class LoanRequirement(models.Model):
    """
        DOCSTRING: LoanRequirement model manages, the official documentation required in order to provide a loan.
    """
    _name = 'loan.manager.requirement'
    _description = 'Loan Requirement'
    _rec_name = 'loan_requirement'
    _inherit = ['mail.thread']

    loan_requirement = fields.Char(string='Nombre del Requisito', required=True, tracking=True)
    description = fields.Char(string='Descripción', required=False, tracking=True)
    mandatory = fields.Boolean(string='Obligatorio', default=False)
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Empresa',
        default=lambda self: self.env.company,
        tracking=True,
        required=True
    )

    _sql_constraints = [
        ('unique_loan_requirement_company', 'UNIQUE(loan_requirement, company_id)', 'El nombre del requisito debe ser único por empresa.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('loan_requirement'):
                vals['loan_requirement'] = vals['loan_requirement'].title()
            if vals.get('description'):
                vals['description'] = vals['description'].capitalize()
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('loan_requirement'):
            vals['loan_requirement'] = vals['loan_requirement'].title()
        if vals.get('description'):
            vals['description'] = vals['description'].capitalize()
        return super().write(vals)


class LoanType(models.Model):
    """
        DOCSTRING: LoanType model manages all the loan products provided by each company.
    """
    _name = 'loan.manager.type'
    _description = 'Loan Type'
    _rec_name = 'loan_name'
    _inherit = ['mail.thread']

    loan_name = fields.Char(string='Nombre de Prestamo', required=True, tracking=True)
    description = fields.Char(string='Descripción', required=False, tracking=True)
    max_amount = fields.Float(string='Monto Maximo', required=True, tracking=True)
    max_tenure = fields.Integer(string='Plazo Maximo', required=True, tracking=True)
    payment_account = fields.Many2one('account.account', string='Cuenta de Cuotas', required=True, tracking=True)
    tenure_plan = fields.Selection([
        ('monthly', 'Mensual'),
        ('biweekly', 'Quincenal'),
        ('weekly', 'Semanal'),
    ], string='Plan de Pago', required=True, tracking=True)
    amortization_method = fields.Selection([
        ('french', 'Cuota Nivelada'),
        ('german', 'Cuota Sobre Saldos Insolutos')
    ], string='Método de Amortización', required=True)
    loan_account = fields.Many2one('account.account', string='Cuenta por Cobrar Cliente', company_dependent=True, domain="[('code', '=ilike', '1%')]", required=True, tracking=True)
    disburse_account = fields.Many2one('account.account', string='Cuenta Provisión de Desembolso', required=True, tracking=True, domain="[('code', '=ilike', '2%')]")
    disburse_bank_account = fields.Many2one('account.account', string='Cuenta Bancaria de Desembolso', domain=[('account_type', '=', 'asset_cash')], required=True, tracking=True)
    disburse_commission = fields.Float(string='Comision por Desembolso (%)', required=True, tracking=True)
    disburse_commission_account = fields.Many2one('account.account', string='Cuenta de Comisión por Desembolso', required=True, tracking=True, domain="[('code', '=ilike', '4%')]")
    anticipated_payment_commission = fields.Float(string='Comision por Pago Anticipado (%)', required=True, tracking=True)
    anticipated_payment_commission_account = fields.Many2one('account.account', string='Cuenta de Comisión por Pago Anticipado', required=True, tracking=True, domain="[('code', '=ilike', '4%')]")
    legal_expenses = fields.Float(string='Gastos Legales', required=True, tracking=True)
    legal_expenses_account = fields.Many2one('account.account', string='Cuenta de Gastos Legales', required=True, tracking=True, domain="['|', ('code', '=ilike', '2%'), ('code', '=ilike', '4%')]")
    life_insurance = fields.Float(string='Seguro de Vida', required=True, tracking=True)
    life_insurance_account = fields.Many2one('account.account', string='Cuenta de Seguro de Vida', required=True, tracking=True, domain="['|', ('code', '=ilike', '2%'), ('code', '=ilike', '4%')]")
    interest_rate = fields.Float(string='Interes (%)', required=True, tracking=True)
    interest_account = fields.Many2one('account.account', string='Cuenta de Interés', required=True, tracking=True, domain="[('code', '=ilike', '4%')]")
    documents = fields.Many2many(
        comodel_name='loan.manager.requirement',
        relation='loan_type_requirement_rel',
        column1='loan_type_id',
        column2='requirement_id',
        string='Documentos Requeridos',
        tracking=True
    )
    criteria = fields.Text(string='Criterios', tracking=True)
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Empresa',
        default=lambda self: self.env.company,
        tracking=True,
        required=True,
    )
    interest_rate_display = fields.Char(string='Tasa de Interes (%)', compute='_compute_interest_rate_display', store=False)

    _sql_constraints = [
        ('unique_loan_type_company', 'UNIQUE(loan_name, company_id)', 'El nombre del préstamo debe ser único por empresa.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._validate_percentage_rates(vals)
            if vals.get('loan_name'):
                vals['loan_name'] = vals['loan_name'].title()
            if vals.get('description'):
                vals['description'] = vals['description'].capitalize()
            if vals.get('criteria'):
                vals['criteria'] = vals['criteria'].capitalize()
        return super().create(vals_list)

    def write(self, vals):
        self._validate_percentage_rates(vals)
        if vals.get('loan_name'):
            vals['loan_name'] = vals['loan_name'].title()
        if vals.get('description'):
            vals['description'] = vals['description'].capitalize()
        if vals.get('criteria'):
            vals['criteria'] = vals['criteria'].capitalize()
        return super().write(vals)

    # Validations
    @api.constrains('max_amount', 'max_tenure')
    def _check_positive_values(self):
        for record in self:
            if record.max_amount <= 0:
                raise ValidationError("El monto máximo debe ser mayor que 0.")
            if record.max_tenure <= 0:
                raise ValidationError("El plazo máximo debe ser mayor que 0.")

    def _validate_percentage_rates(self, vals):
        to_check = {
            'interest_rate': 'Interés',
            'disburse_commission': 'Comisión por desembolso',
            'anticipated_payment_commission': 'Comisión por pago anticipado'
        }
        for field, label in to_check.items():
            if field in vals:
                value = vals[field]
                if value is None:
                    continue
                if value < 0 or value > 100:
                    raise ValidationError(
                        f'El porcentaje de {label} debe estar entre 0% y 100%. Valor recibido: {value}'
                    )
    # UI Changes
    @api.depends('interest_rate')
    def _compute_interest_rate_display(self):
        for record in self:
            record.interest_rate_display = f"{record.interest_rate:.2f}%"

    @api.onchange('company_id')
    def _onchange_company_id(self):
        active_company_id = self.company_id.id or self.env.company.id
        return {
            'domain': {
                'loan_account': [('company_ids', 'in', [active_company_id])]
            }
        }



