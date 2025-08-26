import math
from odoo import models, fields, api
from odoo.exceptions import ValidationError

# Define your models here.


class Loan(models.Model):
    """
        DOCSTRING: Loan model responsible for managing associates loans.
    """

    _name = 'loan.manager.loan'
    _description = 'Loan'
    _rec_name = 'loan_reference'
    _inherit = ['mail.thread']

    loan_reference = fields.Char(string='Referencia', required=True, readonly=True, copy=False, default='LOAN0001')
    partner_id = fields.Many2one('res.partner', string='Cliente', required=True, tracking=True)
    loan_type_id = fields.Many2one('loan.manager.type', string='Tipo de Prestamo', required=True, tracking=True)
    loan_amount = fields.Float(string='Monto', required=True, tracking=True)
    tenure_plan = fields.Selection([
        ('monthly', 'Mensual'),
        ('biweekly', 'Quincenal'),
        ('weekly', 'Semanal'),
    ], string='Plan de Pago', required=True, tracking=True)
    tenure = fields.Integer(string='Plazo', required=True, tracking=True)
    amortization_method = fields.Selection([
        ('french', 'Cuota Nivelada'),
        ('german', 'Cuota Sobre Saldos Insolutos')
    ], string='Método de Amortización')
    interest_rate = fields.Float(string='Tasa de Interes (%)', tracking=True)
    disburse_amount = fields.Float(string='Monto a Desembolsar', readonly=True)
    amount_paid = fields.Float(string="Monto Pagado", compute="_compute_paid_pending", store=False, readonly=True)
    amount_pending = fields.Float(string="Monto Pendiente", compute="_compute_paid_pending", store=False, readonly=True)
    documents_required = fields.Many2many(
        comodel_name='loan.manager.requirement',
        string='Documentos Requeridos',
        compute='_compute_documents_required',
        store=True,
        readonly=True
    )
    loan_status = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('pending', 'Pendiente'),
        ('approved', 'Aprobado'),
        ('registered', 'Contabilizado'),
        ('disbursed', 'Desembolsado'),
        ('declined', 'Denegado')
    ], required=True, default='draft', readonly=True, tracking=True)
    uploaded_documents = fields.One2many(
        'loan.manager.documentation',
        'loan_id',
        string='Documentos Cargados'
    )
    rejection_reason = fields.Text(string="Motivo de Rechazo", readonly=True, tracking=True)
    # Expenses Data
    disburse_commission = fields.Float(string='Comisión por Desembolso (%)')
    disburse_commission_amount = fields.Float(string='Comisión por Desembolso (Monto)', compute='_compute_disburse_commission_amount', store=False, readonly=True, help='Monto calculado como (Monto del préstamo) × (Comisión de desembolso %) / 100.')
    anticipated_payment_commission = fields.Float(string='Comisión por Pago Anticipado (%)')
    legal_expenses = fields.Float(string='Gastos Legales')
    life_insurance = fields.Float(string='Seguro de Vida')
    # Accounts Data
    interest_account_number = fields.Char(string='Cuenta de Interés')
    life_insurance_account_number = fields.Char(string='Cuenta de Seguro de Vida')
    disburse_account_number = fields.Char(string='Cuenta de Desembolso')
    disburse_bank_account_number = fields.Char(string='Cuenta Bancaria de Desembolso')
    payment_account_number = fields.Char(string='Cuenta de Cuotas')
    legal_expenses_account_number = fields.Char(string='Cuenta de Gastos Legales')
    anticipated_payment_commission_account_number = fields.Char(string='Cuenta de Comisión por Pago Anticipado')
    disburse_commission_account_number = fields.Char(string='Cuenta de Comisión por Desembolso')
    register_move_id = fields.Many2one('account.move', string='Asiento de Registro', readonly=True, copy=False)
    disburse_move_id = fields.Many2one('account.move', string='Asiento de Desembolso', readonly=True, copy=False)
    # Related Data
    company_id = fields.Many2one('res.company', readonly=True, copy=False, default=lambda self: self.env.company)
    loan_repayment_ids = fields.One2many('loan.manager.repayment', 'loan_id', string='Cuotas Generadas')
    create_date_only = fields.Date(string="Fecha de Creación", compute="_compute_create_date_only", store=True)
    interest_rate_display = fields.Char(string='Tasa de Interes (%)', compute='_compute_interest_rate_display', store=False)
    repayments_dirty = fields.Boolean(default=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            loan_type_id = vals.get('loan_type_id')
            if loan_type_id:
                loan_type = self.env['loan.manager.type'].browse(loan_type_id)
                if loan_type:
                    vals.update({
                        'interest_rate': loan_type.interest_rate,
                        'disburse_commission': loan_type.disburse_commission,
                        'anticipated_payment_commission': loan_type.anticipated_payment_commission,
                        'legal_expenses': loan_type.legal_expenses,
                        'life_insurance': loan_type.life_insurance,
                        'interest_account_number': loan_type.interest_account.code or '',
                        'life_insurance_account_number': loan_type.life_insurance_account.code or '',
                        'disburse_account_number': loan_type.disburse_account.code or '',
                        'payment_account_number': loan_type.payment_account.code or '',
                        'legal_expenses_account_number': loan_type.legal_expenses_account.code or '',
                        'anticipated_payment_commission_account_number': loan_type.anticipated_payment_commission_account.code or '',
                        'disburse_commission_account_number': loan_type.disburse_commission_account.code or '',
                        'disburse_bank_account_number': (loan_type.disburse_bank_account.code or '') if loan_type.disburse_bank_account else '',
                        'amortization_method': (loan_type.amortization_method or '') if loan_type.amortization_method else '',
                        'tenure_plan': (loan_type.tenure_plan or '') if loan_type.tenure_plan else '',
                    })
            self._validate_loan_constraints(vals)
        return super().create(vals_list)

    def write(self, vals):
        for record in self:
            if vals.get('loan_amount') or vals.get('tenure') or vals.get('interest_rate'):
                vals['repayments_dirty'] = True
            updated_vals = vals.copy()
            loan_type_id = updated_vals.get('loan_type_id') or record.loan_type_id.id
            loan_type = self.env['loan.manager.type'].browse(loan_type_id)
            if loan_type:
                updated_vals.update({
                    'interest_rate': loan_type.interest_rate,
                    'disburse_commission': loan_type.disburse_commission,
                    'anticipated_payment_commission': loan_type.anticipated_payment_commission,
                    'legal_expenses': loan_type.legal_expenses,
                    'life_insurance': loan_type.life_insurance,
                    'interest_account_number': loan_type.interest_account.code or '',
                    'life_insurance_account_number': loan_type.life_insurance_account.code or '',
                    'disburse_account_number': loan_type.disburse_account.code or '',
                    'payment_account_number': loan_type.payment_account.code or '',
                    'legal_expenses_account_number': loan_type.legal_expenses_account.code or '',
                    'anticipated_payment_commission_account_number': loan_type.anticipated_payment_commission_account.code or '',
                    'disburse_commission_account_number': loan_type.disburse_commission_account.code or '',
                    'disburse_bank_account_number': (loan_type.disburse_bank_account.code or '') if loan_type.disburse_bank_account else '',
                    'amortization_method': (loan_type.amortization_method or '') if loan_type.amortization_method else '',
                    'tenure_plan': (loan_type.tenure_plan or '') if loan_type.tenure_plan else '',
                })
            record._validate_loan_constraints(updated_vals)
            super().write(vals)
        return True

    # Automatic Calculations
    @api.depends('loan_type_id')
    def _compute_documents_required(self):
        empty_recordset = self.env['loan.manager.requirement']
        for record in self:
            record.documents_required = (
                record.loan_type_id.documents
                if record.loan_type_id and record.loan_type_id.documents
                else empty_recordset
            )

    @api.depends('create_date')
    def _compute_create_date_only(self):
        for record in self:
            record.create_date_only = record.create_date.date() if record.create_date else False

    @api.depends('interest_rate')
    def _compute_interest_rate_display(self):
        for record in self:
            record.interest_rate_display = f"{record.interest_rate:.2f}%"

    @api.depends('loan_status', 'loan_repayment_ids.status', 'loan_repayment_ids.principal')
    def _compute_paid_pending(self):
        for loan in self:
            if loan.loan_status != 'disbursed':
                loan.amount_paid = 0.0
                loan.amount_pending = 0.0
                continue
            paid = sum(loan.loan_repayment_ids.filtered(lambda r: r.status == 'paid').mapped('principal'))
            pending = sum(loan.loan_repayment_ids.filtered(lambda r: r.status == 'pending').mapped('principal'))
            loan.amount_paid = math.floor(paid)
            loan.amount_pending = math.floor(pending)

    @api.depends('loan_type_id.amortization_method')
    def _compute_method_display(self):
        map_labels = {
            'french': 'Cuota Nivelada',
            'german': 'Cuota Sobre Saldos Insolutos',
        }
        for rec in self:
            method = rec.amortization_method or ''
            rec.method_display = map_labels.get(method, '')

    @api.depends('loan_type_id.tenure_plan')
    def _compute_tenure_plan_display(self):
        map_units = {
            'weekly': 'Semanal',
            'biweekly': 'Quincenal',
            'monthly': 'Mensual',
        }
        for rec in self:
            plan = rec.tenure_plan or ''
            rec.tenure_plan_display = map_units.get(plan, '')

    @api.depends('loan_amount', 'disburse_commission')
    def _compute_disburse_commission_amount(self):
        for rec in self:
            pct = (rec.disburse_commission or 0.0) / 100.0
            base = rec.loan_amount or 0.0
            rec.disburse_commission_amount = round(base * pct, 2)

    # UI Changes
    @api.onchange('loan_type_id')
    def _on_change_type_id(self):
        if self.loan_type_id:
            self.interest_rate = self.loan_type_id.interest_rate
            self.disburse_commission = self.loan_type_id.disburse_commission
            self.anticipated_payment_commission = self.loan_type_id.anticipated_payment_commission
            self.legal_expenses = self.loan_type_id.legal_expenses
            self.life_insurance = self.loan_type_id.life_insurance
            self.amortization_method = self.loan_type_id.amortization_method
            self.tenure_plan = self.loan_type_id.tenure_plan

    # Validations
    def _validate_loan_constraints(self, vals):
        tenure = vals.get('tenure')
        loan_amount = vals.get('loan_amount')
        loan_type_id = vals.get('loan_type_id') or self.loan_type_id.id
        loan_type = self.env['loan.manager.type'].browse(loan_type_id) if loan_type_id else None
        if tenure is not None:
            if tenure <= 0:
                raise ValidationError("El plazo debe ser mayor que cero.")
            if loan_type and loan_type.max_tenure and tenure > loan_type.max_tenure:
                raise ValidationError(f"El plazo no puede superar los {loan_type.max_tenure} meses.")
        if loan_amount is not None:
            if loan_amount <= 0:
                raise ValidationError("El monto del préstamo debe ser mayor que cero.")
            if loan_type and loan_type.max_amount and loan_amount > loan_type.max_amount:
                raise ValidationError(f"El monto no puede superar los {loan_type.max_amount}.")

    def _validate_repayments_before_status_change(self):
        for record in self:
            if not record.loan_repayment_ids:
                raise ValidationError("Debe calcular las cuotas antes de cambiar el estado del préstamo.")

    # Internal Methods
    def _compute_disburse_amount(self):
        for record in self:
            disbursed_commission_amount = record.loan_amount * (record.disburse_commission or 0.0) / 100.0
            total_deductions = disbursed_commission_amount + record.legal_expenses + record.life_insurance
            record.disburse_amount = record.loan_amount - total_deductions

    def _register_loan(self):
        Account = self.env['account.account']
        Move = self.env['account.move']
        Journal = self.env['account.journal']

        for loan in self:
            partner_acc = loan.partner_id.loan_account
            if not partner_acc:
                raise ValidationError("El cliente debe tener definida una Cuenta de Préstamo (loan_account).")
            if loan.company_id not in partner_acc.company_ids:
                raise ValidationError(
                    f"La Cuenta de Préstamo del cliente ({partner_acc.display_name}) "
                    f"no pertenece a la empresa {loan.company_id.name}."
                )

            disburse_commission_amount = (loan.loan_amount or 0.0) * (loan.disburse_commission or 0.0) / 100.0

            required = {
                'disburse_commission_account_number': disburse_commission_amount,
                'legal_expenses_account_number': loan.legal_expenses or 0.0,
                'life_insurance_account_number': loan.life_insurance or 0.0,
                'disburse_account_number': loan.disburse_amount or 0.0,
            }

            lines = [(0, 0, {
                'name': loan.loan_reference,
                'account_id': partner_acc.id,
                'partner_id': loan.partner_id.id,
                'debit': loan.loan_amount,
                'credit': 0.0,
            })]

            for acct_field, amount in required.items():
                if amount > 0:
                    code = getattr(loan, acct_field)
                    if not code:
                        raise ValidationError(f"Falta la cuenta para {acct_field}.")
                    account = Account.search([
                        ('code', '=', code),
                        ('company_ids', 'in', loan.company_id.id),
                    ], limit=1)
                    if not account:
                        raise ValidationError(
                            f"No se encontró la cuenta con código {code} para la empresa {loan.company_id.name}."
                        )
                    lines.append((0, 0, {
                        'name': loan.loan_reference,
                        'account_id': account.id,
                        'debit': 0.0,
                        'credit': amount,
                    }))

            journal = Journal.search([
                ('type', '=', 'general'),
                ('company_id', '=', loan.company_id.id)
            ], limit=1)
            if not journal:
                raise ValidationError(f"No existe un diario general en la empresa {loan.company_id.name}.")

            move = Move.create({
                'ref': f'Préstamo {loan.loan_reference}',
                'date': loan.create_date_only or fields.Date.today(),
                'journal_id': journal.id,
                'company_id': loan.company_id.id,
                'currency_id': loan.company_id.currency_id.id,
                'loan_manager_id': loan.id,
                'line_ids': lines,

            })
            move.action_post()
            loan.write({'register_move_id': move.id})

    def _disburse_loan(self):
        Account = self.env['account.account']
        Move = self.env['account.move']
        Journal = self.env['account.journal']

        for loan in self:
            if loan.disburse_amount <= 0:
                raise ValidationError("El monto a desembolsar debe ser mayor que 0.")

            bank_account = loan.loan_type_id.disburse_bank_account
            if not bank_account:
                raise ValidationError("Defina la cuenta bancaria de desembolso en el Tipo de Préstamo.")
            if bank_account.account_type != 'asset_cash':
                raise ValidationError("La cuenta bancaria de desembolso debe ser de tipo 'Bank & Cash'.")
            if loan.company_id not in bank_account.company_ids:
                raise ValidationError(
                    f"La cuenta bancaria {bank_account.display_name} no pertenece a la empresa {loan.company_id.name}."
                )

            if not loan.disburse_account_number:
                raise ValidationError("Falta la cuenta de Desembolso (código) en el préstamo.")
            disb_account = Account.search([
                ('code', '=', loan.disburse_account_number),
                ('company_ids', 'in', loan.company_id.id),
            ], limit=1)
            if not disb_account:
                raise ValidationError(
                    f"No se encontró la cuenta con código {loan.disburse_account_number} "
                    f"para la empresa {loan.company_id.name}."
                )

            amount = loan.disburse_amount
            lines = [
                (0, 0, {
                    'name': f'Desembolso {loan.loan_reference}',
                    'account_id': disb_account.id,
                    'debit': amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': f'Desembolso {loan.loan_reference}',
                    'account_id': bank_account.id,
                    'debit': 0.0,
                    'credit': amount,
                }),
            ]

            journal = Journal.search([
                ('type', 'in', ('bank', 'cash')),
                ('company_id', '=', loan.company_id.id),
            ], limit=1) or Journal.search([
                ('type', '=', 'general'),
                ('company_id', '=', loan.company_id.id),
            ], limit=1)
            if not journal:
                raise ValidationError(f"No existe un diario para registrar el desembolso en {loan.company_id.name}.")

            move = Move.create({
                'ref': f'Desembolso {loan.loan_reference}',
                'date': loan.create_date_only or fields.Date.today(),
                'journal_id': journal.id,
                'company_id': loan.company_id.id,
                'currency_id': loan.company_id.currency_id.id,
                'loan_manager_id': loan.id,
                'line_ids': lines,
            })
            move.action_post()
            loan.write({'disburse_move_id': move.id})

    # Button Actions
    def action_calculate_repayments(self):
        for loan in self:
            self.env['loan.manager.repayment'].search([('loan_id', '=', loan.id)]).unlink()
            if loan.interest_rate == 0:
                raise ValidationError('La tasa no puede ser igual a 0')
            principal = loan.loan_amount
            rate = (loan.interest_rate / 100) / 12
            months = loan.tenure
            start_date = loan.create_date_only or fields.Date.today()
            method = loan.loan_type_id.amortization_method
            repayments = []
            remaining = principal

            if method == 'french':
                payment = (principal * rate) / (1 - (1 + rate) ** -months)
                for i in range(1, months + 1):
                    interest = remaining * rate
                    capital = payment - interest
                    repayments.append((0, 0, {
                        'sequence': i,
                        'due_date': fields.Date.add(start_date, months=i),
                        'principal': round(capital, 2),
                        'interest': round(interest, 2),
                        'remaining_balance': round(remaining - capital, 2)
                    }))
                    remaining -= capital

            elif method == 'german':
                capital = principal / months
                for i in range(1, months + 1):
                    interest = remaining * rate
                    total = capital + interest
                    repayments.append((0, 0, {
                        'sequence': i,
                        'due_date': fields.Date.add(start_date, months=i),
                        'principal': round(capital, 2),
                        'interest': round(interest, 2),
                        'remaining_balance': round(remaining - capital, 2)
                    }))
                    remaining -= capital

            loan.write({'loan_repayment_ids': repayments})
        self.write({'repayments_dirty': False})

    def action_confirmed(self):
        for record in self:
            record.loan_status = 'confirmed'
            documentation_model = self.env['loan.manager.documentation']
            for requirement in record.documents_required:
                existing = documentation_model.search([
                    ('loan_id', '=', record.id),
                    ('requirement_id', '=', requirement.id)
                ])
                if not existing:
                    documentation_model.create({
                        'loan_id': record.id,
                        'requirement_id': requirement.id,
                        'loan_documentation_reference': 'New',
                        'filename': '',
                        'file': False,
                    })

    def action_pending(self):
        self._validate_repayments_before_status_change()
        for record in self:
            if record.repayments_dirty:
                raise ValidationError("Debe recalcular las cuotas antes de cambiar el estado, ya que ha cambiado el monto, plazo o tasa de interes.")
            mandatory_requirements = record.documents_required.filtered(lambda r: r.mandatory)
            for req in mandatory_requirements:
                doc_uploaded = record.uploaded_documents.filtered(lambda d: d.requirement_id == req and d.file)
                if not doc_uploaded:
                    raise ValidationError(
                        f"Debe cargar el documento obligatorio: '{req.loan_requirement}' antes de solicitar el préstamo.")
            record.loan_status = 'pending'

    def action_approved(self):
        self._validate_repayments_before_status_change()
        for record in self:
            if record.repayments_dirty:
                raise ValidationError("Debe recalcular las cuotas antes de cambiar el estado, ya que ha cambiado el monto, plaza o tasa de interes.")
            record._compute_disburse_amount()
            record.loan_status = 'approved'

    def action_declined(self):
        for record in self:
            record.loan_status = 'declined'

    def action_registered(self):
        self._validate_repayments_before_status_change()
        self._register_loan()
        for record in self:
            record.loan_status = 'registered'

    def action_disbursed(self):
        self._validate_repayments_before_status_change()
        self._disburse_loan()
        for record in self:
            record.loan_status = 'disbursed'


class LoanDocumentation(models.Model):
    """
        DOCSTRING:LoanDocumentation model responsible for holding loan documentation related information.
    """
    _name = 'loan.manager.documentation'
    _description = 'Loan Documentation'
    _rec_name = 'loan_documentation_reference'
    _inherit = ['mail.thread']

    loan_documentation_reference = fields.Char(string='Referencia', required=True, readonly=True, copy=False, default='1')
    loan_id = fields.Many2one('loan.manager.loan', string='Prestamo', required=True, readonly=True, copy=False)
    requirement_id = fields.Many2one('loan.manager.requirement', string='Requisito', required=True, readonly=True, copy=False)
    mandatory = fields.Boolean(related='requirement_id.mandatory', string='Obligatorio', store=False)
    file = fields.Binary(string='Archivo', required=True)
    filename = fields.Char(string='Nombre de Archivo', required=True, readonly=True, copy=False)
    status = fields.Selection([
        ('pending', 'Pendiente'),
        ('presented', 'Presentado'),
    ], default='pending', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            loan = self.env['loan.manager.loan'].browse(vals['loan_id'])
            if loan.loan_status != 'confirmed':
                raise ValidationError("Solo puede subir documentos cuando el préstamo está en estado 'Confirmado'.")
            if vals.get('loan_documentation_reference', 'New') == 'New':
                vals['loan_documentation_reference'] = self.env['ir.sequence'].next_by_code(
                    'loan.documentation') or 'New'
            if vals.get('file') and not vals.get('filename'):
                loan = self.env['loan.manager.loan'].browse(vals['loan_id'])
                requirement = self.env['loan.manager.requirement'].browse(vals['requirement_id'])
                vals['filename'] = f"{loan.partner_id.name} - {requirement.loan_requirement}.pdf"
        return super().create(vals_list)

    def write(self, vals):
        for record in self:
            if record.loan_id.loan_status != 'confirmed':
                raise ValidationError("No se pueden modificar documentos si el préstamo no está en estado 'Confirmado'.")
        if 'file' in vals and not vals.get('filename'):
            loan = self.loan_id
            requirement = self.requirement_id
            vals['filename'] = f"{loan.partner_id.name} - {requirement.loan_requirement}.pdf"
            self.status = 'presented'
        return super().write(vals)

    @api.onchange('file')
    def _onchange_file(self):
        if self.file and self.loan_id.partner_id and self.requirement_id:
            client_name = self.loan_id.partner_id.name
            requirement_name = self.requirement_id.loan_requirement
            self.filename = f"{client_name} - {requirement_name}.pdf"


class LoanRepayment(models.Model):
    """
        DOCSTRING:LoanRepayment model responsible for holding loan payments related information.
    """
    _name = 'loan.manager.repayment'
    _description = 'Loan Repayment'
    loan_id = fields.Many2one('loan.manager.loan', string='Prestamo', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Número de Cuota', required=True)
    due_date = fields.Date(string='Fecha de Pago', required=True)
    principal = fields.Float(string='Capital', required=True)
    interest = fields.Float(string='Interés', required=True)
    total_payment = fields.Float(string='Pago Total', compute='_compute_total_payment', store=True)
    remaining_balance = fields.Float(string='Saldo Restante', required=True)
    loan_status = fields.Selection(related='loan_id.loan_status', store=True)
    status = fields.Selection([
        ('pending', 'Pendiente'),
        ('paid', 'Pagado'),
    ], default='pending', readonly=True, copy=False)
    move_id = fields.Many2one('account.move', string='Asiento', readonly=True, copy=False, ondelete='set null', help='Asiento contable creado al registrar el pago de esta cuota.')

    def write(self, vals):
        allowed = {'status', 'move_id'}
        illegal = set(vals.keys()) - allowed
        if illegal:
            raise ValidationError("Las cuotas no se pueden editar manualmente.")
        return super().write(vals)

    @api.depends('principal', 'interest')
    def _compute_total_payment(self):
        for rec in self:
            rec.total_payment = rec.principal + rec.interest

    def _create_payment_move(self):
        self.ensure_one()
        AccountMove = self.env['account.move']
        Journal = self.env['account.journal']

        rec = self
        loan = rec.loan_id
        company = loan.company_id
        company_currency = company.currency_id
        loan_type = loan.loan_type_id
        partner = loan.partner_id

        if not partner.loan_account:
            raise ValidationError("El contacto no tiene configurada la Cuenta de Préstamos (loan_account).")
        if not loan_type.payment_account:
            raise ValidationError("El Tipo de Préstamo no tiene configurada la Cuenta de Cuotas (payment_account).")
        if not loan_type.interest_account:
            raise ValidationError("El Tipo de Préstamo no tiene configurada la Cuenta de Interés (interest_account).")
        if rec.total_payment <= 0:
            raise ValidationError("El pago total debe ser mayor que 0.")

        journal = Journal.search([
            ('type', 'in', ('bank', 'cash')),
            ('company_id', '=', company.id),
        ], limit=1) or Journal.search([
            ('type', '=', 'general'),
            ('company_id', '=', company.id),
        ], limit=1)
        if not journal:
            raise ValidationError(f"No se encontró un diario para {company.name}.")

        def _line(vals):
            v = dict(vals)
            v.setdefault('currency_id', company_currency.id)
            v.setdefault('amount_currency', (v.get('debit', 0.0) or 0.0) - (v.get('credit', 0.0) or 0.0))
            return v

        lines = [

            (0, 0, _line({
                'name': f'Pago cuota {rec.sequence} {loan.loan_reference}',
                'account_id': loan_type.disburse_bank_account.id,
                'debit': rec.total_payment,
                'credit': 0.0,
            })),

            (0, 0, _line({
                'name': f'Capital cuota {rec.sequence} {loan.loan_reference}',
                'account_id': partner.loan_account.id,
                'partner_id': partner.id,
                'debit': 0.0,
                'credit': rec.principal,
            })),

            (0, 0, _line({
                'name': f'Interés cuota {rec.sequence} {loan.loan_reference}',
                'account_id': loan_type.interest_account.id,
                'debit': 0.0,
                'credit': rec.interest,
            })),
        ]

        move = AccountMove.create({
            'ref': f'Pago cuota {rec.sequence} {loan.loan_reference}',
            'date': rec.due_date or fields.Date.today(),
            'journal_id': journal.id,
            'company_id': company.id,
            'currency_id': company_currency.id,
            'line_ids': lines,
        })
        move.action_post()
        return move

    def action_mark_as_paid(self):
        for record in self:
            previous_unpaid = self.env['loan.manager.repayment'].search([
                ('loan_id', '=', record.loan_id.id),
                ('sequence', '<', record.sequence),
                ('status', '=', 'pending'),
            ])
            if previous_unpaid:
                raise ValidationError(
                    f"No puede marcar como pagada la cuota #{record.sequence} porque la cuota #{previous_unpaid[0].sequence} aún está pendiente."
                )
            move = record._create_payment_move()
            record.write({'status': 'paid', 'move_id': move.id})


class LoanRepaymentConfirmWizard(models.TransientModel):
    """
        DOCSTRING: LoanRepaymentConfirmWizard Transient Model responsible for confirming payments.
    """
    _name = 'loan.manager.repayment.confirm.wizard'
    _description = 'Confirmar pago de cuota'

    repayment_id = fields.Many2one('loan.manager.repayment', required=True, readonly=True)
    principal = fields.Float(string='Capital', readonly=True)
    interest = fields.Float(string='Interés', readonly=True)
    total_to_pay = fields.Float(string='Total a Pagar', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        repayment = self.env['loan.manager.repayment'].browse(self.env.context.get('active_id'))
        if repayment:
            res.update({
                'repayment_id': repayment.id,
                'principal': repayment.principal,
                'interest': repayment.interest,
                'total_to_pay': repayment.total_payment,
            })
        return res

    def action_confirm(self):
        self.ensure_one()
        r = self.repayment_id.sudo()
        if r.loan_status != 'disbursed' or r.status != 'pending':
            raise ValidationError("Solo puede pagar cuotas pendientes de préstamos desembolsados.")
        r.action_mark_as_paid()
        return {'type': 'ir.actions.act_window_close'}


class LoanRejectWizard(models.TransientModel):
    """
        DOCSTRING:LoanRejectWizard transient model responsible for capturing information about rejections and setting it to the loan modal.
    """
    _name = 'loan.manager.reject.wizard'
    _description = 'Rechazar Préstamo'

    loan_id = fields.Many2one('loan.manager.loan', string='Préstamo', required=True, ondelete='cascade')
    reason = fields.Text(string='Motivo del Rechazo', required=True)

    def action_confirm(self):
        self.ensure_one()
        loan = self.loan_id.sudo()
        if loan.loan_status not in ('pending',):
            raise ValidationError("Solo puede rechazar préstamos en estado Pendiente.")
        loan.write({
            'loan_status': 'declined',
            'rejection_reason': self.reason,
        })
        return {'type': 'ir.actions.act_window_close'}


