// Dashboard JavaScript
const API_BASE_URL = '/api';

// Chart instances
let typeChart = null;
let trendChart = null;
let currentFilter = 'all';

// Pagination
let currentPage = 1;
const itemsPerPage = 10;
let cachedProjects = [];

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    loadDashboardData();
    // Auto refresh every 5 minutes
    setInterval(loadDashboardData, 5 * 60 * 1000);
});

// Load all dashboard data
async function loadDashboardData() {
    try {
        // Load stats
        const stats = await fetchJSON(`${API_BASE_URL}/stats`);
        updateStats(stats);

        // Load type distribution
        const typeData = await fetchJSON(`${API_BASE_URL}/by-type`);
        updateTypeChart(typeData);

        // Load daily trend
        const trendData = await fetchJSON(`${API_BASE_URL}/daily-trend`);
        updateTrendChart(trendData);

        // Load scheduler logs
        const logs = await fetchJSON(`${API_BASE_URL}/scheduler-logs`);
        updateSchedulerLogs(logs);

        // Load recent projects
        const projects = await fetchJSON(`${API_BASE_URL}/recent-projects`);
        cachedProjects = projects;  // 缓存数据
        currentPage = 1;  // 重置到第一页
        updateRecentProjects(projects);

        // Update last update time
        document.getElementById('last-update').textContent = new Date().toLocaleString('zh-CN');

    } catch (error) {
        console.error('Failed to load dashboard data:', error);
        showError('加载数据失败，请检查后端服务');
    }
}

// Fetch JSON data
async function fetchJSON(url) {
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    return await response.json();
}

// Update statistics cards
function updateStats(data) {
    document.getElementById('total-records').textContent = data.total.toLocaleString();
    document.getElementById('today-new').textContent = data.today_new.toLocaleString();
    document.getElementById('week-new').textContent = data.week_new.toLocaleString();
    document.getElementById('month-new').textContent = data.month_new.toLocaleString();
}

// Update type distribution chart
function updateTypeChart(data) {
    const ctx = document.getElementById('typeChart').getContext('2d');

    const labels = Object.keys(data);
    const values = Object.values(data);
    const colors = ['#3b82f6', '#10b981', '#f59e0b'];

    if (typeChart) {
        typeChart.destroy();
    }

    typeChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: colors,
                borderWidth: 0,
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 15,
                        usePointStyle: true,
                        font: {
                            size: 12,
                            family: 'Noto Sans SC'
                        },
                        generateLabels: function(chart) {
                            const data = chart.data;
                            const dataset = data.datasets[0];
                            const total = dataset.data.reduce((a, b) => a + b, 0);

                            return data.labels.map((label, i) => {
                                const value = dataset.data[i];
                                const percentage = ((value / total) * 100).toFixed(1);
                                return {
                                    text: `${label}: ${value} (${percentage}%)`,
                                    fillStyle: dataset.backgroundColor[i],
                                    hidden: false,
                                    index: i,
                                    fontColor: '#666',
                                    strokeStyle: '#fff',
                                    lineWidth: 2
                                };
                            });
                        }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((value / total) * 100).toFixed(1);
                            return `${label}: ${value} (${percentage}%)`;
                        }
                    }
                }
            },
            cutout: '65%'
        }
    });
}

// Update trend chart
function updateTrendChart(data) {
    const ctx = document.getElementById('trendChart').getContext('2d');

    if (trendChart) {
        trendChart.destroy();
    }

    trendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [{
                label: '新增记录数',
                data: data.values,
                borderColor: '#667eea',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointRadius: 4,
                pointBackgroundColor: '#667eea',
                pointBorderColor: '#fff',
                pointBorderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        font: {
                            size: 11,
                            family: 'Noto Sans SC'
                        }
                    }
                },
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    },
                    ticks: {
                        font: {
                            size: 11,
                            family: 'Noto Sans SC'
                        }
                    }
                }
            }
        }
    });
}

// Update scheduler logs
function updateSchedulerLogs(logs) {
    const container = document.getElementById('scheduler-logs');

    if (!logs || logs.length === 0) {
        container.innerHTML = '<div class="text-gray-500 text-center py-4">暂无调度日志</div>';
        return;
    }

    const statusIcons = {
        'success': { color: 'text-green-500', icon: '✓' },
        'running': { color: 'text-blue-500', icon: '◉' },
        'error': { color: 'text-red-500', icon: '✗' }
    };

    container.innerHTML = logs.map(log => {
        const status = statusIcons[log.status] || statusIcons['running'];
        return `
            <div class="log-item p-3 mb-2 rounded-lg">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                        <span class="${status.color} font-bold">${status.icon}</span>
                        <span class="font-medium text-gray-700">${log.step || '调度任务'}</span>
                    </div>
                    <span class="text-xs text-gray-400">${formatTime(log.timestamp)}</span>
                </div>
                <div class="text-sm text-gray-500 mt-1 pl-5">
                    ${log.message || log.details || ''}
                </div>
                ${log.records_processed ? `
                    <div class="text-xs text-gray-400 mt-1 pl-5">
                        处理了 ${log.records_processed} 条记录
                    </div>
                ` : ''}
            </div>
        `;
    }).join('');
}

// Update recent projects
function updateRecentProjects(projects) {
    const container = document.getElementById('recent-projects');

    // Filter projects if needed
    let filteredProjects = projects;
    if (currentFilter !== 'all') {
        filteredProjects = projects.filter(p => p.info_type === currentFilter);
    }

    if (!filteredProjects || filteredProjects.length === 0) {
        container.innerHTML = '<div class="text-gray-500 text-center py-8">暂无项目数据</div>';
        updatePagination(0);
        return;
    }

    const typeClasses = {
        '招标计划': 'type-jihua',
        '招标公告': 'type-zhaobiao',
        '中标候选人公示': 'type-zhongbiao'
    };

    // 计算分页
    const totalItems = filteredProjects.length;
    const totalPages = Math.ceil(totalItems / itemsPerPage);
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = Math.min(startIndex + itemsPerPage, totalItems);
    const pageItems = filteredProjects.slice(startIndex, endIndex);

    container.innerHTML = pageItems.map(project => {
        const typeClass = typeClasses[project.info_type] || 'type-zhaobiao';
        // 对标题进行HTML转义，防止XSS和破坏属性
        const safeTitle = project.title ? project.title.replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;') : '';
        return `
            <div class="project-card p-4 mb-3 rounded-xl border border-gray-100 hover:shadow-md cursor-pointer"
                 data-url="${project.original_url || ''}"
                 onclick="window.open(this.dataset.url || '#', '_blank')">
                <div class="flex items-start justify-between gap-3">
                    <div class="flex-1 min-w-0">
                        <h4 class="font-medium text-gray-800 text-sm line-clamp-2 mb-2" title="${safeTitle}">
                            ${project.title || '无标题'}
                        </h4>
                        <div class="flex items-center gap-3 text-xs text-gray-500">
                            <span class="type-badge ${typeClass}">${project.info_type || '未知'}</span>
                            <span class="flex items-center gap-1">
                                <svg class="w-3 h-3" viewBox="0 0 20 20" fill="currentColor">
                                    <path fill-rule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clip-rule="evenodd"/>
                                </svg>
                                ${project.region || '未知地区'}
                            </span>
                            <span class="flex items-center gap-1">
                                <svg class="w-3 h-3" viewBox="0 0 20 20" fill="currentColor">
                                    <path fill-rule="evenodd" d="M6 2a1 1 0 00-1 1v1H4a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2h-1V3a1 1 0 10-2 0v1H7V3a1 1 0 00-1-1zm0 5a1 1 0 000 2h8a1 1 0 100-2H6z" clip-rule="evenodd"/>
                                </svg>
                                ${formatDate(project.publish_time)}
                            </span>
                        </div>
                    </div>
                    <div class="flex flex-col items-end gap-1">
                        ${project.sent_to_feishu ?
                            `<span class="text-xs text-green-500 flex items-center gap-1">
                                <svg class="w-3 h-3" viewBox="0 0 20 20" fill="currentColor">
                                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
                                </svg>
                                已通知
                            </span>` :
                            `<span class="text-xs text-gray-400">待发送</span>`
                        }
                        ${project.extracted_data ?
                            `<span class="text-xs text-indigo-500">已提取</span>` :
                            `<span class="text-xs text-gray-400">未提取</span>`
                        }
                    </div>
                </div>
            </div>
        `;
    }).join('');

    // 更新分页指示器
    updatePagination(totalPages);
}

// 更新分页指示器
function updatePagination(totalPages) {
    const pageIndicator = document.getElementById('page-indicator');
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');

    if (totalPages === 0) {
        pageIndicator.textContent = '第 1 页 / 共 1 页';
        prevBtn.disabled = true;
        nextBtn.disabled = true;
        return;
    }

    pageIndicator.textContent = `第 ${currentPage} 页 / 共 ${totalPages} 页`;
    prevBtn.disabled = currentPage <= 1;
    nextBtn.disabled = currentPage >= totalPages;
}

// 上一页
function prevPage() {
    if (currentPage > 1) {
        currentPage--;
        updateRecentProjects(cachedProjects);
    }
}

// 下一页
function nextPage() {
    const filteredProjects = currentFilter === 'all'
        ? cachedProjects
        : cachedProjects.filter(p => p.info_type === currentFilter);
    const totalPages = Math.ceil(filteredProjects.length / itemsPerPage);

    if (currentPage < totalPages) {
        currentPage++;
        updateRecentProjects(cachedProjects);
    }
}

// Filter projects by type
function filterType(type) {
    currentFilter = type;
    currentPage = 1;  // 筛选时重置到第一页

    // 更新所有筛选按钮样式
    const buttons = document.querySelectorAll('.filter-btn');
    buttons.forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.type === type) {
            btn.classList.add('active');
        }
    });

    // 使用缓存的数据更新显示
    updateRecentProjects(cachedProjects);
}

// Show project detail - open original URL
function showProjectDetail(project) {
    if (typeof project === 'string') {
        // 如果是ID字符串，需要通过API获取详情
        fetchJSON(`${API_BASE_URL}/project/${project}`).then(projectData => {
            if (projectData.original_url) {
                window.open(projectData.original_url, '_blank');
            } else {
                alert('无法获取项目链接');
            }
        }).catch(() => {
            alert('获取项目详情失败');
        });
    } else if (project && project.original_url) {
        // 如果是对象且包含original_url，直接打开
        window.open(project.original_url, '_blank');
    }
}

// Refresh data
function refreshData() {
    const btn = document.querySelector('button[onclick="refreshData()"]');
    btn.disabled = true;
    btn.innerHTML = `
        <svg class="w-5 h-5 animate-spin" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        刷新中...
    `;

    loadDashboardData().then(() => {
        btn.disabled = false;
        btn.innerHTML = `
            <svg class="w-5 h-5" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            刷新数据
        `;
    });
}

// Export data
function exportData() {
    window.open(`${API_BASE_URL}/export`, '_blank');
}

// Utility: Format date
function formatDate(dateStr) {
    if (!dateStr) return '未知';
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return dateStr;
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
}

// Utility: Format time
function formatTime(timestamp) {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    if (isNaN(date.getTime())) return timestamp;
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}

// Utility: Show error
function showError(message) {
    // Simple alert for now, could be replaced with a toast
    console.error(message);
}
